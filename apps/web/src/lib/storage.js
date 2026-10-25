// localStorage puede no existir (modo privado, almacenamiento bloqueado): nunca rompe la página.
export function storageGet(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

export function storageSet(key, value) {
  try { localStorage.setItem(key, value); } catch { /* sin almacenamiento: solo se pierde la preferencia */ }
}

export function browserStorage() {
  try { return localStorage; } catch { return null; }
}
