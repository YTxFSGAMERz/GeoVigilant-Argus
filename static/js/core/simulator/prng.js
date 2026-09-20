export class SeededPRNG {
  constructor(seed = 0x1337c0de) {
    this.s0 = this.splitmix32(seed);
    this.s1 = this.splitmix32(this.s0);
    this.s2 = this.splitmix32(this.s1);
    this.s3 = this.splitmix32(this.s2);
  }

  splitmix32(a) {
    a |= 0;
    a = (a + 0x9e3779b9) | 0;
    let t = a ^ (a >>> 16);
    t = Math.imul(t, 0x21f0aaad);
    t = t ^ (t >>> 15);
    t = Math.imul(t, 0x735a2d97);
    return (t ^ (t >>> 15)) >>> 0;
  }

  nextFloat() {
    const result = ((this.s0 + this.s3) >>> 0) / 4294967296;
    const t = (this.s1 << 9) >>> 0;

    this.s2 ^= this.s0;
    this.s3 ^= this.s1;
    this.s1 ^= this.s2;
    this.s0 ^= this.s3;

    this.s2 ^= t;
    this.s3 = ((this.s3 << 11) | (this.s3 >>> 21)) >>> 0;

    return result;
  }

  nextGaussian(mean = 0, stdDev = 1) {
    const u1 = Math.max(1e-15, this.nextFloat());
    const u2 = this.nextFloat();
    const z0 = Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
    return mean + z0 * stdDev;
  }

  nextRange(min, max) {
    return min + this.nextFloat() * (max - min);
  }
}
