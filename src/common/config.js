// Base URL of the analytics backend (FastAPI). Imported by the background
// service worker (which posts watch events) and the popup (which reads stats).
// Change this one constant to point at a deployed API later.
export const API_BASE = 'http://localhost:8000';
