addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

const securityHeaders = {
  "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline' https:; style-src 'self' 'unsafe-inline' https:; img-src 'self' data: https:; font-src 'self' https:; connect-src 'self' https:; frame-ancestors 'none'; base-uri 'self'; object-src 'none'",
  "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "X-Content-Type-Options": "nosniff",
  "Permissions-Policy": "geolocation=(), microphone=(), camera=(), interest-cohort=()",
  "Cache-Control": "public, max-age=3600"
}

async function handleRequest(request) {
  // Forward the request to origin (bypasses cache unless Cloudflare route/proxy handles caching)
  const response = await fetch(request)

  // Clone response headers and add/overwrite security headers
  const newHeaders = new Headers(response.headers)
  for (const [k, v] of Object.entries(securityHeaders)) {
    newHeaders.set(k, v)
  }

  // Return new response with same body and status, but updated headers
  const resp = new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: newHeaders
  })
  return resp
}
