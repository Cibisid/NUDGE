import { useState } from "react";

export default function App() {
  const [task, setTask] = useState("");
  const [link, setLink] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!task) return;
    setLoading(true);
    setLink("");
    try {
      const response = await fetch("http://127.0.0.1:8000/create-agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task }),
      });
      const data = await response.json();
      setLink(data.link);
    } catch (error) {
      alert("Error connecting to server!");
    }
    setLoading(false);
  };

  const copyLink = () => {
    navigator.clipboard.writeText(link);
    alert("Link copied!");
  };

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontFamily: "Arial, sans-serif"
    }}>
      <div style={{
        background: "white",
        borderRadius: "20px",
        padding: "40px",
        width: "90%",
        maxWidth: "500px",
        boxShadow: "0 20px 60px rgba(0,0,0,0.3)"
      }}>
        <h1 style={{ textAlign: "center", color: "#333", marginBottom: "10px" }}>
          👆 NUDGE
        </h1>
        <p style={{ textAlign: "center", color: "#666", marginBottom: "30px" }}>
          Describe a task → Send a link → It does everything automatically
        </p>

        <textarea
          placeholder="e.g. Open Chrome and search for the weather in Jacksonville"
          value={task}
          onChange={(e) => setTask(e.target.value)}
          rows={4}
          style={{
            width: "100%",
            padding: "15px",
            borderRadius: "10px",
            border: "2px solid #eee",
            fontSize: "16px",
            resize: "none",
            boxSizing: "border-box",
            outline: "none"
          }}
        />

        <button
          onClick={handleSubmit}
          disabled={loading}
          style={{
            width: "100%",
            padding: "15px",
            marginTop: "15px",
            background: loading ? "#ccc" : "linear-gradient(135deg, #667eea, #764ba2)",
            color: "white",
            border: "none",
            borderRadius: "10px",
            fontSize: "18px",
            cursor: loading ? "not-allowed" : "pointer",
            fontWeight: "bold"
          }}
        >
          {loading ? "🤖 Generating..." : "⚡ Generate Link"}
        </button>

        {link && (
          <div style={{
            marginTop: "25px",
            background: "#f8f8ff",
            borderRadius: "10px",
            padding: "20px",
            border: "2px solid #667eea"
          }}>
            <p style={{ color: "#333", fontWeight: "bold", marginBottom: "10px" }}>
              ✅ Your NUDGE link is ready!
            </p>
            <p style={{
              wordBreak: "break-all",
              color: "#667eea",
              fontSize: "14px",
              marginBottom: "15px"
            }}>
              {link}
            </p>
            <div style={{ display: "flex", gap: "10px" }}>
              <button
                onClick={copyLink}
                style={{
                  flex: 1,
                  padding: "10px",
                  background: "#667eea",
                  color: "white",
                  border: "none",
                  borderRadius: "8px",
                  cursor: "pointer",
                  fontSize: "14px"
                }}
              >
                📋 Copy Link
              </button>
              <button
                onClick={() => window.open(link, "_blank")}
                style={{
                  flex: 1,
                  padding: "10px",
                  background: "#764ba2",
                  color: "white",
                  border: "none",
                  borderRadius: "8px",
                  cursor: "pointer",
                  fontSize: "14px"
                }}
              >
                🚀 Run Now
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}