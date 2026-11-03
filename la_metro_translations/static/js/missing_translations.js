document.addEventListener("DOMContentLoaded", () => {
  const buttons = document.querySelectorAll(".missing-list button")
  buttons.forEach((b) => console.log("found a button", b.dataset.language))
  buttons.forEach((b) =>
    b.addEventListener("click", () => {
      console.log(b.dataset.language)
    })
  )
})
