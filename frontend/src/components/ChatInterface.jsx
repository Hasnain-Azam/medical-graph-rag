/**
 * ChatInterface — the Q&A chat panel.
 * Sends questions to the GraphRAG pipeline and displays answers with source chips.
 * Also triggers graph visualization updates via onGraphUpdate.
 */
import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { sendQuery } from "../services/api";

const SAMPLE_QUESTIONS = [
  "How is Metformin used in Type 2 Diabetes treatment?",
  "What blood tests diagnose Type 2 Diabetes?",
  "Which genes are associated with insulin resistance?",
  "What is the ADA stepwise treatment protocol?",
  "How does Empagliflozin protect the kidneys?",
];

function formatTime(date) {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function ChatInterface({ onGraphUpdate }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = "auto";
      ta.style.height = `${Math.min(ta.scrollHeight, 120)}px`;
    }
  }, [input]);

  const handleSend = async (questionOverride) => {
    const question = (questionOverride || input).trim();
    if (!question || isLoading) return;

    const userMessage = {
      id: Date.now(),
      role: "user",
      content: question,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const data = await sendQuery(question);

      const assistantMessage = {
        id: Date.now() + 1,
        role: "assistant",
        content: data.answer,
        sources: data.sources || [],
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Push subgraph to visualization panel
      if (data.subgraph) {
        onGraphUpdate?.(data.subgraph, "query");
      }
    } catch (err) {
      const errorMessage = {
        id: Date.now() + 1,
        role: "assistant",
        content: `**Error:** ${err.message}\n\nPlease make sure you've uploaded a document first and that the backend is running.`,
        sources: [],
        timestamp: new Date(),
        isError: true,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-container">
      {/* Panel Header */}
      <div className="panel-section">
        <h3>💬 Knowledge Graph Q&amp;A</h3>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 && !isLoading ? (
          <div className="chat-empty">
            <div className="chat-empty-icon">🔬</div>
            <h4>Ask a medical question</h4>
            <p>
              Upload a document above, then ask questions. The AI will search
              the knowledge graph and provide a grounded answer while visualizing
              the relevant graph on the right.
            </p>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className={`message ${msg.role}`}>
              <div className="message-avatar">
                {msg.role === "user" ? "👤" : "🤖"}
              </div>
              <div className="message-content">
                <div className="message-bubble">
                  {msg.role === "assistant" ? (
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  ) : (
                    msg.content
                  )}
                </div>

                {/* Source entity chips */}
                {msg.sources?.length > 0 && (
                  <div className="message-sources">
                    {msg.sources.slice(0, 6).map((src) => (
                      <span key={src} className="source-chip">
                        {src}
                      </span>
                    ))}
                  </div>
                )}

                <div className="message-time">{formatTime(msg.timestamp)}</div>
              </div>
            </div>
          ))
        )}

        {/* Loading indicator */}
        {isLoading && (
          <div className="message assistant">
            <div className="message-avatar">🤖</div>
            <div className="message-content">
              <div className="message-bubble loading-bubble">
                <div className="loading-dot" />
                <div className="loading-dot" />
                <div className="loading-dot" />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Sample Questions */}
      {messages.length === 0 && (
        <div className="sample-questions">
          <div className="sample-q-label">Try asking</div>
          {SAMPLE_QUESTIONS.map((q) => (
            <button
              key={q}
              className="sample-q-btn"
              onClick={() => handleSend(q)}
              disabled={isLoading}
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="chat-input-area">
        <div className="chat-input-row">
          <textarea
            ref={textareaRef}
            className="chat-input"
            placeholder="Ask about diseases, drugs, genes, treatments..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={isLoading}
          />
          <button
            className="send-button"
            onClick={() => handleSend()}
            disabled={!input.trim() || isLoading}
            title="Send (Enter)"
          >
            ➤
          </button>
        </div>
        <div className="chat-hint">Enter to send · Shift+Enter for new line</div>
      </div>
    </div>
  );
}
