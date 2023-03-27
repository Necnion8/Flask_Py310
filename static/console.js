
document.addEventListener("DOMContentLoaded", () => {
    var sock = io();
    var term = new Terminal();
    term.open(document.querySelector("#terminal"));

    sock.on("connect", () => {
        console.log("Connected Socket.IO");
    });

    sock.on("disconnect", () => {
        console.log("Disconnected Socket.IO");
    });

    sock.on("term_data", (data) => {
        term.write(data.raw);
    });

    var input = document.querySelector("#input");
    document.querySelector("#inputForm").addEventListener("submit", (event) => {
        event.preventDefault();
        var inputText = input.value.trim();
        if (!inputText) {
            return;
        }

        sock.emit("term_send_text", { text: inputText });
        input.value = "";
    });

});
