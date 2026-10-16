# StyleVision

A personalized virtual fashion and beauty styling system — MCA Capstone Project.

## Tech Stack
- **Frontend**: React Native 0.81 · Expo SDK 54 · TypeScript 5.9 · Expo Router
- **Backend**: Python 3.12 · FastAPI · uvicorn
- **Database**: MongoDB 8.x · motor (async driver)
- **AI / CV**: MediaPipe · OpenCV · Pillow · NumPy · CatVTON (GPU environment required)

---

## Prerequisites

| Tool | Version |
|------|---------|
| Node.js | ≥ 20 |
| Python | 3.12 |
| MongoDB | Running locally on port 27017 |
| Expo Go | Latest (on your phone) |

---

## Quick Start

### 1. Clone and enter the project
```bash
git clone <your-repo-url>
cd StyleVision
```

### 2. Start MongoDB
Make sure MongoDB is running locally:
```bash
# Windows — run in a separate terminal
mongod
```

### 3. Backend setup
```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

pip install -r requirements.txt
copy .env.example .env
# Edit .env and fill in your values

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
API docs available at: http://localhost:8000/docs

### 4. Frontend setup
```bash
cd frontend
npm install
copy .env.example .env
# Edit .env and set EXPO_PUBLIC_API_URL to your backend IP

npx expo start
```
Scan the QR code with Expo Go on your phone, or press `w` for web.

---

## Project Structure
```
StyleVision/
├── frontend/        # React Native + Expo app
├── backend/         # FastAPI backend
│   ├── app/         # Application code
│   ├── uploads/     # User-uploaded images (gitignored)
│   └── catalogue/   # Style catalogue assets
├── docs/            # Architecture and API documentation
└── README.md
```

---

## AI Features — Hardware Note

The CatVTON clothing try-on model requires an **NVIDIA GPU with ≥ 8 GB VRAM**.  
On CPU-only machines, the application runs in **prototype overlay mode** (clearly labelled).  
For real GPU inference, connect the backend to a Google Colab T4 GPU environment.

---

## Environment Variables

See `backend/.env.example` and `frontend/.env.example` for all required variables.  
**Never commit `.env` files with real secrets.**
