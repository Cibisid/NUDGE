# 👆 NUDGE — AI-Powered Remote Automation Agent

> Describe a task in plain English → Get a secure link → Send it → It executes automatically on the target device. No app install needed.

## 🎯 Problem It Solves
Ever had to video call your parents just to help them do something simple on their PC? NUDGE fixes that. You describe the task, AI generates an automation agent, you send a link, and it runs automatically on their device.

## 🚀 Demo
1. Type: "Open notepad and type Hello World"
2. Click Generate Link
3. Open the link on any Windows PC
4. Watch it execute automatically 🤖

## ⚙️ How It Works
1. User describes a task in plain English
2. LLM (Llama 3.3 70B via Groq) generates a Python automation script
3. A unique secure token link is created
4. Link opens on target device and executes the script automatically
5. Task done — zero technical knowledge needed

## 🛠️ Tech Stack
- **Backend:** Python, FastAPI, Groq API (Llama 3.3 70B)
- **Frontend:** React, Vite
- **Automation:** PyAutoGUI, Subprocess
- **Security:** UUID token links with expiry

## 📦 Installation

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## 🔑 Environment Variables
Create a `backend/.env` file: