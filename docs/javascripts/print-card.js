document.addEventListener("click", (event) => {
  if (event.target.closest(".print-card")) {
    window.print();
  }
});

