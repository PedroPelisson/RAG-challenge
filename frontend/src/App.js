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

      const data = await response.json()
      const botMessage = { role: 'bot', text: data.answer};
      setMessage((prev) => [...prev, botMessage]);

    } catch (err) {
      const errorMessage = { role: 'bot', text: 'Erro de conexão' };
      setMessage((prev) => [...prev, errorMessage]);
    }

    setLoading(false)
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !loading) {
      handleSend();
    }
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
                      <li key={i}>{name}</li>
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
              <div key={index} className={`message ${msg.role}`}>
                <strong>{msg.role === 'user' ? 'Você: ' : 'Greg: '}</strong>
                {msg.role === 'bot' ? <ReactMarkdown>{msg.text}</ReactMarkdown> : <p>{msg.text}</p>}
              </div>
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