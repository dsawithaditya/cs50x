const crypto = require('crypto');
const bcrypt = require('bcryptjs');

/**
 * Verifies a password against Werkzeug scrypt, pbkdf2, or bcrypt hash.
 */
function checkPasswordHash(storedHash, password) {
  if (!storedHash || !password) return false;

  // Werkzeug scrypt format: scrypt:32768:8:1$salt$hexhash
  if (storedHash.startsWith('scrypt:')) {
    try {
      const parts = storedHash.split('$');
      if (parts.length !== 3) return false;
      const [prefix, salt, hexHash] = parts;
      const prefixParts = prefix.split(':');
      const n = parseInt(prefixParts[1], 10) || 32768;
      const r = parseInt(prefixParts[2], 10) || 8;
      const p = parseInt(prefixParts[3], 10) || 1;

      const expectedBuf = Buffer.from(hexHash, 'hex');
      const keyLen = expectedBuf.length;
      const derived = crypto.scryptSync(password, salt, keyLen, {
        N: n,
        r: r,
        p: p,
        maxmem: 256 * 1024 * 1024
      });
      return crypto.timingSafeEqual(expectedBuf, derived);
    } catch (err) {
      console.error('Error checking scrypt hash:', err);
      return false;
    }
  }

  // Werkzeug pbkdf2 format: pbkdf2:sha256:iterations$salt$hexhash
  if (storedHash.startsWith('pbkdf2:')) {
    try {
      const parts = storedHash.split('$');
      if (parts.length !== 3) return false;
      const [prefix, salt, hexHash] = parts;
      const prefixParts = prefix.split(':');
      const iterations = parseInt(prefixParts[2], 10) || 260000;
      const digest = prefixParts[1] || 'sha256';

      const expectedBuf = Buffer.from(hexHash, 'hex');
      const keyLen = expectedBuf.length;
      const derived = crypto.pbkdf2Sync(password, salt, iterations, keyLen, digest);
      return crypto.timingSafeEqual(expectedBuf, derived);
    } catch (err) {
      console.error('Error checking pbkdf2 hash:', err);
      return false;
    }
  }

  // Bcrypt format: $2a$, $2b$, $2y$
  if (storedHash.startsWith('$2')) {
    try {
      return bcrypt.compareSync(password, storedHash);
    } catch (err) {
      return false;
    }
  }

  // Fallback direct string match (for unhashed legacy dev records)
  return storedHash === password;
}

/**
 * Generates a Werkzeug-compatible scrypt password hash.
 */
function generatePasswordHash(password) {
  const salt = crypto.randomBytes(16).toString('base64').replace(/[^a-zA-Z0-9]/g, '').slice(0, 16);
  const n = 32768;
  const r = 8;
  const p = 1;
  const keyLen = 64;
  const derived = crypto.scryptSync(password, salt, keyLen, {
    N: n,
    r: r,
    p: p,
    maxmem: 256 * 1024 * 1024
  });
  return `scrypt:${n}:${r}:${p}$${salt}$${derived.toString('hex')}`;
}

module.exports = {
  checkPasswordHash,
  generatePasswordHash
};
