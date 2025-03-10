"""
Key implementation files for multiprocess LLM-RPG
"""

# ===========================================================
# File: engine/npc_process_manager.py
# ===========================================================

import logging
import time
import os
from multiprocessing import Process, Queue, Manager
from typing import Dict, List, Any, Optional

import config

logger = logging.getLogger("llm_rpg.process_manager")

class NPCProcessManager:
    """Manages NPC processes"""

    def __init__(self, npcs, llm_model=config.DEFAULT_MODEL):
        self.npcs = npcs
        self.processes = {}
        self.command_queues = {}
        self.response_queues = {}
        self.shared_manager = Manager()
        self.shared_state = self.shared_manager.dict()
        self.llm_model = llm_model

        # Initialize shared state
        self.shared_state["game_running"] = True

        logger.info(f"Process Manager initialized with {len(npcs)} NPCs")

    def start_processes(self):
        """Start a process for each NPC"""
        from engine.npc_process import npc_process_main

        for npc in self.npcs:
            cmd_queue = Queue()
            resp_queue = Queue()

            # Create and start the process
            proc = Process(
                target=npc_process_main,
                args=(npc.id, cmd_queue, resp_queue, self.shared_state, self.llm_model),
                daemon=True,
                name=f"NPC-{npc.name}"
            )
            proc.start()

            # Store process and queues
            self.processes[npc.id] = proc
            self.command_queues[npc.id] = cmd_queue
            self.response_queues[npc.id] = resp_queue

            # Send initial NPC data
            self.send_command(npc.id, "update_npc", npc.to_dict())

            logger.info(f"Started process for NPC: {npc.name}")

    def stop_processes(self):
        """Stop all NPC processes"""
        # Update shared state to indicate game is stopping
        self.shared_state["game_running"] = False

        for npc_id, queue in self.command_queues.items():
            # Send shutdown command
            queue.put({"command": "shutdown"})

        # Wait for processes to terminate
        for npc_id, proc in self.processes.items():
            proc.join(timeout=1.0)
            if proc.is_alive():
                logger.warning(f"Terminating process for NPC: {npc_id}")
                proc.terminate()

        logger.info("All NPC processes stopped")

    def send_command(self, npc_id, command, data=None):
        """Send a command to an NPC process"""
        if npc_id in self.command_queues:
            try:
                self.command_queues[npc_id].put({
                    "command": command,
                    "data": data
                })
                return True
            except Exception as e:
                logger.error(f"Error sending command to NPC {npc_id}: {str(e)}")
                return False
        return False

    def get_responses(self, timeout=0.0):
        """Collect responses from all NPC processes"""
        responses = {}

        for npc_id, queue in self.response_queues.items():
            try:
                # Non-blocking check for responses
                if not queue.empty():
                    responses[npc_id] = queue.get(block=False)
            except Exception as e:
                logger.error(f"Error getting response from NPC {npc_id}: {str(e)}")

        return responses

    def get_response(self, npc_id, timeout=5.0):
        """Wait for a response from a specific NPC with timeout"""
        if npc_id not in self.response_queues:
            return None

        try:
            start_time = time.time()
            while time.time() - start_time < timeout:
                if not self.response_queues[npc_id].empty():
                    return self.response_queues[npc_id].get(block=False)
                time.sleep(0.1)  # Small delay to prevent CPU overuse
        except Exception as e:
            logger.error(f"Error waiting for response from NPC {npc_id}: {str(e)}")

        return None

    def update_shared_state(self, key, value):
        """Update a value in the shared state"""
        self.shared_state[key] = value

    def check_process_health(self):
        """Check if all processes are healthy and restart any that aren't"""
        for npc_id, proc in list(self.processes.items()):
            if not proc.is_alive():
                logger.warning(f"NPC process {npc_id} died, restarting")

                # Get the NPC object
                npc = None
                for n in self.npcs:
                    if n.id == npc_id:
                        npc = n
                        break

                if npc:
                    # Create new queues
                    cmd_queue = Queue()
                    resp_queue = Queue()

                    # Start a new process
                    from engine.npc_process import npc_process_main
                    new_proc = Process(
                        target=npc_process_main,
                        args=(npc_id, cmd_queue, resp_queue, self.shared_state, self.llm_model),
                        daemon=True,
                        name=f"NPC-{npc.name}"
                    )
                    new_proc.start()

                    # Update process and queues
                    self.processes[npc_id] = new_proc
                    self.command_queues[npc_id] = cmd_queue
                    self.response_queues[npc_id] = resp_queue

                    # Send initial NPC data
                    self.send_command(npc_id, "update_npc", npc.to_dict())

                    logger.info(f"Restarted process for NPC: {npc.name}")

    # Add a method to check and update NPC statuses
    def update_npc_statuses(self):
        """Check and update the status of all NPC processes"""
        # Handle the case where npcs is a list
        if isinstance(self.npcs, list):
            for npc in self.npcs:
                # Skip if NPC doesn't have an ID
                if not hasattr(npc, 'id'):
                    continue

                npc_id = npc.id

                # Skip if NPC doesn't have a process
                if npc_id not in self.processes:
                    continue

                # Check if NPC is active
                is_active = npc.is_active() if hasattr(npc, 'is_active') else True

                if not is_active:
                    # Update the process with the current status
                    status = getattr(npc, 'status', 'unknown')
                    self.send_command(npc_id, "set_status", status)
                    logger.debug(f"Updated process status for {npc.name}: {status}")

    # Add a method to stop processes for specific NPCs
    def stop_npc_process(self, npc_id):
        """Stop the process for a specific NPC"""
        if npc_id in self.processes:
            # Send shutdown command
            self.send_command(npc_id, "shutdown")

            # Wait for process to terminate
            self.processes[npc_id].join(timeout=1.0)
            if self.processes[npc_id].is_alive():
                logger.warning(f"Terminating process for NPC: {npc_id}")
                self.processes[npc_id].terminate()

            # Remove process and queues
            del self.processes[npc_id]
            del self.command_queues[npc_id]
            del self.response_queues[npc_id]

            logger.info(f"Stopped process for NPC: {npc_id}")
            return True

        return False

    # Add a method to pause/suspend processes for inactive NPCs
    def suspend_inactive_npcs(self):
        """Suspend processes for inactive NPCs to save resources"""
        for npc_id, npc in self.npcs.items():
            # Skip if NPC doesn't have a process
            if npc_id not in self.processes:
                continue

            # Check if NPC is active
            is_active = npc.is_active() if hasattr(npc, 'is_active') else True

            if not is_active:
                # Instead of stopping, we can put the process in a suspended state
                self.send_command(npc_id, "suspend")
                logger.debug(f"Suspended process for inactive NPC: {npc.name}")
