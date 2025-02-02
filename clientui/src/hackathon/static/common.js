function scroll_to(tag) {
    location.hash = "#" + tag;
}

function toggleDiv(id) {
    var div = document.getElementById(id);
    div.style.display = div.style.display == "none" ? "block" : "none";
    div.classList.toggle("col-md-6");
    var mapButton = document.getElementById("map-button");
    mapButton.innerText = mapButton.innerText === "<" ? ">" : "<";
    document.getElementById("chat-toggle").classList.toggle("col-md-6");
  }