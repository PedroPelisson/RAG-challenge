import './App.css';
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';

function App() {
  const [strategy, setStrategy] = useState('v1');
  const [sessionId, setSessionId] = useState(null);
  const [file, setFile] = useState([]);
  const [question, setQuestion] = useState('');
  const [message, setMessage] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploadInfo, setUploadInfo] = useState(null);
  const [pendingDecision, setPendingDecision] = useState(null); // NOVO: guarda conflitos de hash
  const API_URL = 'http://localhost:8000';

  const parseResponse = (text) => {
    let thinkMatch = text.match(/<pensamento>\s*([\s\S]*?)\s*<\/pensamento>/i);
    let answerMatch = text.match(/<resposta>\s*([\s\S]*?)\s*<\/resposta>/i);

    if (!answerMatch) {
      answerMatch = text.match(/<resposta>\s*([\s\S]*)/i);
    }

    if (!thinkMatch) {
      thinkMatch = text.match(/<pensamento>\s*([\s\S]*?)(?=<resposta>|$)/i);
    }

    if (answerMatch) {
      return {
        thinking: thinkMatch ? thinkMatch[1].trim() : '',
        answer: answerMatch[1].trim()
      };
    }

    const cleanText = text
      .replace(/<\/?pensamento>/gi, '')
      .replace(/<\/?resposta>/gi, '')
      .trim();
    return { thinking: '', answer: cleanText };
  };

  const handleStrategyChange = (e) => {
    setStrategy(e.target.value);
    setSessionId(null);
    setMessage([]);
    setUploadInfo(null);
    setPendingDecision(null);
    setFile([]);
  }

  const handleUpload = async () => {
    if (file.length === 0) {
      alert('Selecione um arquivo primeiro');
      return;
    }

    setLoading(true);
    setUploadInfo(null);
    setMessage([]);
    setSessionId(null);
    setPendingDecision(null);

    const formData = new FormData();
    for (let i = 0; i < file.length; i++) {
      formData.append('files', file[i]);
    }
    formData.append('strategy', strategy)

    try {
      const response = await fetch(`${API_URL}/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        alert('Erro:' + error.detail);
        setLoading(false);
        return;
      }

      const data = await  response.json();
      if (data.status === 'pending_decision') {
        setSessionId(data.session_id);
        setPendingDecision(data);
      } else {
        setSessionId(data.session_id);
        setUploadInfo(data);
      }

    } catch (err) {
      alert('Erro de conexão')
    }

    setLoading(false)

  };

  const handleDecision = async(decision) => {
    setLoading(true);
    setPendingDecision(null)

    try{
      const response = await fetch(`${API_URL}/upload/decide`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          decision: decision,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        alert('Erro: ' + error.detail);
        setLoading(false);
        return;
      }

      const data = await response.json();
      setUploadInfo({
        ...data,
        message: decision === 'reuse'
        ? 'Reutilizando semantic chunking'
        : 'Processando com recursive chunking'
      });

    } catch (err) {
      alert('Erro de conexao');
    }

    setLoading(false);
  };

  const handleStartV3 = async () => {
    setLoading(true);
    setUploadInfo(null);
    setMessage([]);
    setSessionId(null);

    try {
      const response = await fetch(`${API_URL}/start-v3`, {
        method: 'POST',
      });

      if (!response.ok) {
        const error = await response.json();
        alert('Erro: ' + error.detail);
        setLoading(false);
        return;
      }

      const data = await response.json();
      setSessionId(data.session_id);
      setUploadInfo(data);

    } catch (err) {
      alert('Erro de conexao')
    }
    setLoading(false)
  }

const handleDeleteCompany = async (company) => {
  const confirmed = window.confirm(
      `Tem certeza que deseja remover "${company}" do banco?\n\nTodos os chunks, hashes e metadados dessa empresa serão excluídos permanentemente.`
    );

    if (!confirmed) return;

    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/delete-company`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company: company }),
      });

      if (!response.ok) {
        const error = await response.json();
        alert('Erro: ' + error.detail);
        setLoading(false);
        return;
      }

      const data = await response.json();

      setUploadInfo((prev) => ({
        ...prev,
        companies: data.remaining_companies,
        message: `"${company}" removida. ${data.chunks_removed} chunks excluídos.`
      }));

    } catch (err) {
      alert('Erro de conexão');
    }

    setLoading(false);
  };


const handleSend = async () => {
    if (!question.trim()) return;
    if (!sessionId) {
      alert('Faça um upload');
      return;
    }

    const userMessage = { role: 'user', text: question };
    setMessage((prev) => [...prev, userMessage]);
    setQuestion('');
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          question: question,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        const errorMessage = { role: 'bot', text: 'Erro: ' + error.detail };
        setMessage((prev) => [...prev, errorMessage]);
        setLoading(false);
        return;
      }

      const data = await response.json();

      if (data.strategy === 'v3' && data.results) {
        const botMessages = data.results.map((r) => ({
          role: 'bot',
          text: r.answer,
          company: r.company,
          context_docs: r.context_docs || []
        }));
        setMessage((prev) => [...prev, ...botMessages]);
      } else {
        const botMessage = {
          role: 'bot',
          text: data.answer,
          context_docs: data.context_docs || []
        };
        setMessage((prev) => [...prev, botMessage]);
      }

    } catch (err) {
      const errorMessage = { role: 'bot', text: 'Erro de conexão' };
      setMessage((prev) => [...prev, errorMessage]);
    }

    setLoading(false);
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !loading) {
      handleSend();
    }
  };

const BotMessage = ({ msg }) => {
  const [showThinking, setShowThinking] = useState(false);
  const parsed = parseResponse(msg.text);

  return (
    <div className='message bot'>
      {msg.company && (
        <div className='company-tag'>{msg.company}</div>
      )}

      <strong>Greg:</strong>

       {(parsed.thinking || (msg.context_docs && msg.context_docs.length > 0)) && (
        <button
          className='btn-thinking'
          onClick={() => setShowThinking(!showThinking)}
        >
          {showThinking ? '−' : '+'}
        </button>
      )}

      {showThinking && (
        <div className='thinking-section'>
          {parsed.thinking && (
            <div className='thinking-content'>
              <strong>Raciocínio:</strong>
              <ReactMarkdown>{parsed.thinking}</ReactMarkdown>
            </div>
          )}
          {msg.context_docs && msg.context_docs.length > 0 && (
            <div className='chunks-content'>
              <strong>Chunks selecionados:</strong>
              {msg.context_docs.map((doc, i) => (
                <div key={i} className='chunk-item'>
                  <span className='chunk-tag'>
                    {doc.company && `[${doc.company}]`} Chunk {i + 1}
                  </span>
                  <p>{doc.content}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className='final-answer'>
        <ReactMarkdown>{parsed.answer}</ReactMarkdown>
      </div>
    </div>
  );
};

  return (
    <div className='app'>
      <aside className='sidebar'>

        <h1>Missão RAG</h1>

        <div className='config-section'>
          <div className='strategy-selector'>
            <label>Estratégia: </label>
            <select
              value={strategy}
              onChange={handleStrategyChange}
              disabled={loading}
            >
              <option value='v1'>v1 - Rápida (Recursive Chunking)</option>
              <option value='v2'>v2 - Persistente (Semantic + Hybrid)</option>
              <option value='v3'>v3 - Banco Completo (Por Empresa)</option>
            </select>
          </div>

          {strategy !== 'v3' && (
            <div className='upload-section'>
              <input
                type='file'
                accept='.pdf'
                multiple
                onChange={(e) => setFile(Array.from(e.target.files))}
                disabled={loading}
              />
              <button className='btn-dark' onClick={handleUpload} disabled={loading || file.length === 0}>
                {loading && !sessionId ? 'Processando...' : 'Processar PDFs'}
              </button>
            </div>
          )}

          {strategy === 'v3' && (
            <div className='upload-section'>
              <p>V3 consulta todos os documentos já processados.</p>
              <button className='btn-dark' onClick={handleStartV3} disabled={loading || sessionId}>
                {loading ? 'Carregando...' : 'Iniciar Chat'}
              </button>
            </div>
          )}

          {pendingDecision && (
            <div className='decision-section'>
              <p><strong>Arquivo já processado anteriormente!</strong></p>
              {pendingDecision.hash_conflicts.map((conflict, i) => (
                <p key={i}>{conflict.filename} {conflict.already_processed_as && `(${conflict.already_processed_as})`}</p>
              ))}
              <p>Deseja reutilizar os chunks existentes (v2) ou continuar com recursive chunking (v1)?</p>
              <div className='decision-buttons'>
                <button className='btn-purple' onClick={() => handleDecision('reuse')} disabled={loading}>
                  Reutilizar (v2)
                </button>
                <button className='btn-dark' onClick={() => handleDecision('continue')} disabled={loading}>
                  Continuar (v1)
                </button>
              </div>
            </div>
          )}

          {uploadInfo && (
            <div className='upload-info'>
              {uploadInfo.status === 'ready' && strategy === 'v3' ? (
                <>
                  <p>{uploadInfo.message}</p>
                  <p>Empresas disponíveis:</p>
                  <ul>
                    {uploadInfo.companies && uploadInfo.companies.map((name, i) => (
                      <li key={i} className='company-list-item'>
                        <span>{name}</span>
                        <button
                          className='btn-delete-company'
                          onClick={() => handleDeleteCompany(name)}
                          disabled={loading}
                          title={`Remover ${name}`}
                        >
                          ✕
                        </button>
                      </li>
                    ))}
                  </ul>
                </>
              ) : uploadInfo.message ? (
                <p>{uploadInfo.message}</p>
              ) : (
                <>
                  <p>Feito! {uploadInfo.file_count} arquivo(s) enviado(s).</p>
                  <ul>
                    {uploadInfo.filenames && uploadInfo.filenames.map((name, i) => (
                      <li key={i}>{name}</li>
                    ))}
                  </ul>
                  <p>Estratégia: {uploadInfo.strategy}</p>
                  <p>Chunks gerados: {uploadInfo.chunks}</p>
                </>
              )}
            </div>
          )}
        </div>
      </aside>

      <main className='chat-area'>
        <div className='chat-section'>
          <div className='messages'>
            {message.length === 0 && sessionId && (
              <p className='empty-chat'></p>
            )}
            {message.map((msg, index) => (
              msg.role === 'user' ? (
                <div key={index} className='message user'>
                  <strong>Você: </strong>
                  <p>{msg.text}</p>
                </div>
              ) : (
                <BotMessage key={index} msg={msg} />
              )
            ))}
            {loading && sessionId && (
              <div className='message-bot'>
                <strong>Greg:</strong>
                <p>Pensando...</p>
              </div>
            )}
          </div>

          <div className='input-section'>
            <input
              type='text'
              placeholder={sessionId ? 'Digite sua pergunta' : 'Após processar os arquivos, digite aqui'}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyPress}
              disabled={!sessionId || loading}
            />
            <button className='btn-purple' onClick={handleSend} disabled={!sessionId || loading || !question.trim()}>
              Enviar
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;