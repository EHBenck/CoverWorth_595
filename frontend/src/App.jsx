import { useEffect, useState } from 'react'
import './App.css'

function App() {
  const [backendStatus, setBackendStatus] = useState('Checking backend...')

  useEffect(() => {
    fetch('/api/health/')
      .then((response) => {
        if (!response.ok) {
          throw new Error('Backend request failed')
        }

        return response.json()
      })
      .then((data) => {
        setBackendStatus(data.message)
      })
      .catch((error) => {
        console.error(error)
        setBackendStatus('Backend connection failed')
      })
  }, [])

  return (
    <main>
      <h1>CoverWorth</h1>

      <p>Frontend is running.</p>

      <p>
        Backend status: <strong>{backendStatus}</strong>
      </p>
    </main>
  )
}

export default App