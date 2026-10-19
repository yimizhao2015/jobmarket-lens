// "Contact Us" form in the footer of every page: fills each <div class="contact"> and sends through Web3Forms,
// which emails the message to the site owner. The access key is public by design (it can only send to that inbox).
(function () {
  const KEY = "";   // Web3Forms access key; until it is set the form shows but cannot send
  document.querySelectorAll(".contact").forEach(el => {
    el.innerHTML = `<form class="contact-form" novalidate>
      <h2>Contact Us</h2>
      <div class="cf-row"><input name="name" placeholder="Name" autocomplete="name" required aria-label="Name">
        <input name="email" type="email" placeholder="Email" autocomplete="email" required aria-label="Email"></div>
      <textarea name="message" rows="3" placeholder="Message" required aria-label="Message"></textarea>
      <input type="checkbox" name="botcheck" class="cf-hp" tabindex="-1" autocomplete="off" aria-hidden="true">
      <div class="cf-row cf-end"><span class="cf-status" role="status"></span>
        <button type="submit"${KEY ? "" : " disabled"}>${KEY ? "Send" : "Coming soon"}</button></div>
    </form>`;
    const f = el.querySelector("form"), st = el.querySelector(".cf-status"), btn = f.querySelector("button");
    f.addEventListener("submit", async e => {
      e.preventDefault();
      if (!KEY) return;
      if (!f.checkValidity()) { st.textContent = "Please fill in your name, a valid email and a message."; return; }
      const d = Object.fromEntries(new FormData(f));
      if (d.botcheck) return;
      btn.disabled = true; st.textContent = "Sending…";
      try {
        const r = await fetch("https://api.web3forms.com/submit", {
          method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ access_key: KEY, subject: "JobMarket Lens: message from " + d.name, from_name: "JobMarket Lens",
            name: d.name, email: d.email, message: d.message, page: location.href }),
        });
        const j = await r.json();
        if (!j.success) throw new Error(j.message);
        f.reset(); st.textContent = "Thanks, your message was sent.";
      } catch { st.textContent = "Sorry, the message could not be sent. Please try again later."; }
      btn.disabled = false;
    });
  });
})();
