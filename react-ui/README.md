# React UI (react-ui)

1. Install deps:
   - cd react-ui
   - npm install

2. Run backend API (from repo root):
   - python main.py --serve --port 5000

3. Start UI:
   - npm run dev
   - Open http://localhost:3001

Notes:
- If backend is on a different host/port, set VITE_API_URL in react-ui/.env (e.g. VITE_API_URL=http://localhost:5000).
- For production, build with npm run build and serve the dist.
