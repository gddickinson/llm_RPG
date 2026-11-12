// Python's random.Random in JavaScript: the MT19937 generator seeded exactly as CPython seeds it from an integer
// (init_by_array over the 32-bit words of abs(seed)), plus getrandbits(k <= 32), _randbelow(n) and choice(seq).
// Copied from the go repo's web kit. Here it lets the offline NPC dialog pick the same lines as the game (talk_engine.test.mjs).
const N = 624, M = 397;

export class PyRandom {
  constructor(seed = 0) { this.mt = new Uint32Array(N); this.mti = N + 1; this.seed(seed); }

  initGenrand(s) {
    const mt = this.mt;
    mt[0] = s >>> 0;
    for (let i = 1; i < N; i++) {
      const p = mt[i - 1] ^ (mt[i - 1] >>> 30);
      mt[i] = (Math.imul(1812433253, p) + i) >>> 0;
    }
    this.mti = N;
  }

  seed(seed) {
    let n = BigInt(seed);
    if (n < 0n) n = -n;
    const key = [];
    while (n > 0n) { key.push(Number(n & 0xffffffffn)); n >>= 32n; }
    if (!key.length) key.push(0);
    this.initGenrand(19650218);
    const mt = this.mt;
    let i = 1, j = 0;
    for (let k = Math.max(N, key.length); k; k--) {
      const p = mt[i - 1] ^ (mt[i - 1] >>> 30);
      mt[i] = ((mt[i] ^ Math.imul(p, 1664525)) + key[j] + j) >>> 0;
      i++; j++;
      if (i >= N) { mt[0] = mt[N - 1]; i = 1; }
      if (j >= key.length) j = 0;
    }
    for (let k = N - 1; k; k--) {
      const p = mt[i - 1] ^ (mt[i - 1] >>> 30);
      mt[i] = ((mt[i] ^ Math.imul(p, 1566083941)) - i) >>> 0;
      i++;
      if (i >= N) { mt[0] = mt[N - 1]; i = 1; }
    }
    mt[0] = 0x80000000;
  }

  uint32() {
    const mt = this.mt;
    if (this.mti >= N) {
      let kk = 0, y;
      for (; kk < N - M; kk++) {
        y = (mt[kk] & 0x80000000) | (mt[kk + 1] & 0x7fffffff);
        mt[kk] = mt[kk + M] ^ (y >>> 1) ^ (y & 1 ? 0x9908b0df : 0);
      }
      for (; kk < N - 1; kk++) {
        y = (mt[kk] & 0x80000000) | (mt[kk + 1] & 0x7fffffff);
        mt[kk] = mt[kk + (M - N)] ^ (y >>> 1) ^ (y & 1 ? 0x9908b0df : 0);
      }
      y = (mt[N - 1] & 0x80000000) | (mt[0] & 0x7fffffff);
      mt[N - 1] = mt[M - 1] ^ (y >>> 1) ^ (y & 1 ? 0x9908b0df : 0);
      this.mti = 0;
    }
    let y = mt[this.mti++];
    y ^= y >>> 11;
    y ^= (y << 7) & 0x9d2c5680;
    y ^= (y << 15) & 0xefc60000;
    y ^= y >>> 18;
    return y >>> 0;
  }

  getrandbits(k) {
    if (k < 1 || k > 32) throw new RangeError('getrandbits: 1 <= k <= 32 supported');
    return this.uint32() >>> (32 - k);
  }

  // CPython's _randbelow_with_getrandbits: rejection sampling on bit_length(n) bits.
  randbelow(n) {
    const k = 32 - Math.clz32(n);
    let r = this.getrandbits(k);
    while (r >= n) r = this.getrandbits(k);
    return r;
  }

  // random.randint(a, b) = a + _randbelow(b - a + 1)
  randint(a, b) { return a + this.randbelow(b - a + 1); }

  choice(seq) {
    if (!seq.length) throw new RangeError('Cannot choose from an empty sequence');
    return seq[this.randbelow(seq.length)];
  }
}
