const obeserver = new IntersectionObserver((enteries) => {
    enteries.forEach((entry) => {
        console.log(entry)
        if (entry.isIntersecting) {
            entry.target.classList.toggle('show', entry.isIntersecting);;
        } else {
            entry.target.classList.remove('show');
        }
    }); 
});

const hiddenElements = document.querySelectorAll('.hidden');
hiddenElements.forEach((el) => obeserver.observe(el));



const handleOnMouseMove = e => {
    const { currentTarget: target } = e;

    const rect = target.getBoundingClientRect()
        x = e.clientX - rect.left,
        y= e.clientY - rect.top;

    target.style.setProperty("--mouse-x", `${x}px`);
    target.style.setProperty("--mouse-y", `${y}px`);
}

for (const card of document.querySelectorAll(".card")) {
    card.onmousemove = e => handleOnMouseMove(e);
}