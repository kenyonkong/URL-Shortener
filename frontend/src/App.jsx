import { useEffect, useState } from 'react'

function App() {
  const [url, setUrl] = useState('')
  const [shortenedUrl, setShortenedUrl] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [urls, setUrls] = useState([])
  const [shortUrlInput, setShortUrlInput] = useState('')
  const [redirectError, setRedirectError] = useState('')
  const [isRedirecting, setIsRedirecting] = useState(false)

  useEffect(() => {
    async function loadUrls() {
      try {
        const response = await fetch('/api/urls')
        if (!response.ok) {
          throw new Error(`Could not load URLs (${response.status}).`)
        }
        setUrls(await response.json())
      } catch (error) {
        setError(error.message)
      }
    }

    loadUrls()
  }, [])

  async function shortenUrl(event) {
    event.preventDefault()
    setError('')
    setShortenedUrl('')
    setIsSubmitting(true)

    try {
      const response = await fetch('/api/shorten', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      })
      if (!response.ok) {
        throw new Error(
          response.status === 422
            ? 'Enter a valid HTTP or HTTPS URL.'
            : `Request failed (${response.status}).`,
        )
      }

      const data = await response.json()
      setShortenedUrl(data.shortened_url)
      setUrls((currentUrls) => [
        data,
        ...currentUrls.filter((item) => item.short_code !== data.short_code),
      ])
    } catch (error) {
      setError(error.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  async function visitShortUrl(event) {
    event.preventDefault()
    setRedirectError('')
    setIsRedirecting(true)

    try {
      const parsedUrl = new URL(shortUrlInput)
      const pathParts = parsedUrl.pathname.split('/').filter(Boolean)
      if (!['http:', 'https:'].includes(parsedUrl.protocol) || pathParts.length !== 1) {
        throw new Error('Enter a valid shortened URL.')
      }

      const response = await fetch(`/api/resolve/${encodeURIComponent(pathParts[0])}`, {
        method: 'POST',
      })
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('This shortened URL does not exist.')
        }
        if (response.status === 429) {
          throw new Error('This shortened URL has reached its visit limit.')
        }
        throw new Error(`Could not open URL (${response.status}).`)
      }

      const data = await response.json()
      window.location.assign(data.original_url)
    } catch (error) {
      setRedirectError(
        error instanceof TypeError ? 'Enter a valid shortened URL.' : error.message,
      )
    } finally {
      setIsRedirecting(false)
    }
  }

  return (
    <main className="app-shell">
      <section className="shortener-card" aria-labelledby="shortener-title">
        <p className="eyebrow">URL shortener</p>
        <h1 id="shortener-title">Make a short link</h1>
        <form onSubmit={shortenUrl}>
          <label htmlFor="url">URL to shorten</label>
          <input
            id="url"
            type="url"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://example.com/a/long/path"
            required
          />
          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Shortening…' : 'Shorten URL'}
          </button>
        </form>
        <div className="result" aria-live="polite">
          {shortenedUrl && (
            <p>
              Short link: <a href={shortenedUrl}>{shortenedUrl}</a>
            </p>
          )}
          {error && <p className="error">{error}</p>}
        </div>
        <h2>Visit a short URL</h2>
        <form onSubmit={visitShortUrl}>
          <label htmlFor="short-url">Short URL</label>
          <input
            id="short-url"
            type="text"
            value={shortUrlInput}
            onChange={(event) => setShortUrlInput(event.target.value)}
            placeholder="http://127.0.0.1:8000/aB3dE9z"
            required
          />
          <button type="submit" disabled={isRedirecting}>
            {isRedirecting ? 'Checking…' : 'Visit URL'}
          </button>
        </form>
        <div className="redirect-result" role="status" aria-live="polite">
          {redirectError && <p className="error">{redirectError}</p>}
        </div>
        <h2>Created URLs</h2>
        {urls.length > 0 ? (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Original URL</th>
                  <th>Short URL</th>
                </tr>
              </thead>
              <tbody>
                {urls.map((item) => (
                  <tr key={item.short_code}>
                    <td>
                      <a href={item.original_url}>{item.original_url}</a>
                    </td>
                    <td>
                      <a href={item.shortened_url}>{item.shortened_url}</a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="empty-state">No shortened URLs yet.</p>
        )}
      </section>
    </main>
  )
}

export default App
