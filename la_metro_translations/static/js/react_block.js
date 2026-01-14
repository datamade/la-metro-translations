import React from "react"
import { createRoot } from "react-dom/client"

function ExampleComponent() {
  return <h2 className="text-center bg-info-subtle p-5">Hello from React!</h2>
}

const container = document.querySelector('div[id$="react-block"]')
const root = createRoot(container)
root.render(<ExampleComponent />)
