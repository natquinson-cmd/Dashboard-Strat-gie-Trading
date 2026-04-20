// Cloudflare Worker: Handler du formulaire de contact
// - Reçoit la soumission POST depuis le site
// - Envoie un email de notification à l'équipe (natquinson + mimi.deco7)
// - Envoie un email d'accusé de réception stylé au visiteur
// Utilise Brevo (https://api.brevo.com/v3/smtp/email)

const CORS_HEADERS = {
  // Same-origin via route emilie-quinson.com/api/contact, mais on laisse
  // les headers CORS pour permettre les tests depuis d'autres origines si besoin
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Max-Age": "86400",
};

function escapeHtml(s = "") {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

async function sendViaBrevo(env, payload) {
  const r = await fetch("https://api.brevo.com/v3/smtp/email", {
    method: "POST",
    headers: {
      "api-key": env.BREVO_API_KEY,
      "Content-Type": "application/json",
      "Accept": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const txt = await r.text();
    throw new Error(`Brevo ${r.status}: ${txt.substring(0, 200)}`);
  }
  return r.json();
}

function buildNotificationEmail(env, { prenom, email, message }) {
  const to = env.NOTIFY_EMAILS.split(",").map((e) => ({ email: e.trim() }));
  const html = `
<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;color:#56585e;line-height:1.6;max-width:600px;margin:0 auto;padding:24px;">
<h2 style="color:#56585e;">Nouveau message depuis le site</h2>
<p><strong>Prénom :</strong> ${escapeHtml(prenom) || "(non renseigné)"}</p>
<p><strong>Email :</strong> <a href="mailto:${escapeHtml(email)}">${escapeHtml(email)}</a></p>
<p><strong>Message :</strong></p>
<div style="background:#f8f5ef;padding:16px;border-radius:8px;white-space:pre-wrap;">${escapeHtml(message)}</div>
<hr style="margin:24px 0;border:none;border-top:1px solid #eee;">
<p style="font-size:12px;color:#999;">Envoyé automatiquement via le formulaire de contact d'emilie-quinson.com</p>
</body></html>`;
  return {
    sender: { email: env.FROM_EMAIL, name: env.FROM_NAME },
    replyTo: { email, name: prenom || email },
    to,
    subject: `Nouveau message de ${prenom || email} - Choisis la vie`,
    htmlContent: html,
  };
}

function buildAutoReplyEmail(env, { prenom, email }) {
  const displayName = prenom ? escapeHtml(prenom) : "";
  const greeting = displayName ? `Bonjour ${displayName},` : "Bonjour,";
  const logoUrl = "https://emilie-quinson.com/wp-content/uploads/2026/03/hero-emilie-1.png";

  const html = `<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Merci pour votre message</title>
</head>
<body style="margin:0;padding:0;background:#f8f5ef;font-family:'Helvetica Neue',Arial,sans-serif;color:#56585e;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f8f5ef;padding:40px 20px;">
  <tr><td align="center">
    <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.06);">
      <!-- Bandeau logo -->
      <tr><td align="center" style="background:#ffffff;padding:40px 20px 20px;">
        <img src="${logoUrl}" alt="Choisis la vie - Emilie Quinson" width="220" style="max-width:220px;height:auto;display:block;margin:0 auto;">
      </td></tr>
      <!-- Bandeau rose -->
      <tr><td style="background:#f2ceca;padding:30px 40px;text-align:center;">
        <h1 style="margin:0;font-family:Georgia,'Times New Roman',serif;font-size:28px;color:#56585e;font-weight:400;font-style:italic;">Votre message a bien été reçu</h1>
      </td></tr>
      <!-- Corps -->
      <tr><td style="padding:40px;background:#ffffff;">
        <p style="margin:0 0 20px;font-size:17px;color:#56585e;">${greeting}</p>
        <p style="margin:0 0 18px;font-size:16px;line-height:1.7;color:#56585e;">
          Merci infiniment d'avoir pris le temps de m'écrire. Votre message est entre de bonnes mains, et je l'ai bien reçu.
        </p>
        <p style="margin:0 0 18px;font-size:16px;line-height:1.7;color:#56585e;">
          Je vous lirai avec soin et reviendrai vers vous dans les prochains jours. Sachez que votre démarche, quelle qu'elle soit, est précieuse à mes yeux.
        </p>
        <p style="margin:0 0 28px;font-size:16px;line-height:1.7;color:#56585e;">
          Que Dieu vous garde et vous bénisse en attendant notre échange.
        </p>
        <p style="margin:0 0 8px;font-size:16px;color:#56585e;">À très vite,</p>
        <p style="margin:0 0 4px;font-size:18px;color:#56585e;font-weight:600;">Emilie Quinson</p>
        <p style="margin:0;font-size:15px;color:#b07878;font-style:italic;">Choisis la vie</p>
      </td></tr>
      <!-- Footer -->
      <tr><td style="background:#f8f5ef;padding:24px 40px;text-align:center;border-top:1px solid #eee6d9;">
        <p style="margin:0 0 8px;font-size:13px;color:#8a8c92;">
          <a href="https://emilie-quinson.com" style="color:#b07878;text-decoration:none;">emilie-quinson.com</a>
        </p>
        <p style="margin:0;font-size:12px;color:#a8aab0;">
          Cet email est une réponse automatique — merci de ne pas y répondre directement.
        </p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>`;

  return {
    sender: { email: env.FROM_EMAIL, name: env.FROM_NAME },
    to: [{ email, name: prenom || email }],
    subject: "Votre message a bien été reçu - Emilie Quinson",
    htmlContent: html,
  };
}

export default {
  async fetch(request, env, ctx) {
    // Preflight CORS
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }
    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405, headers: CORS_HEADERS });
    }

    // Parse body (supporte FormData et JSON)
    let data = {};
    const ct = request.headers.get("content-type") || "";
    try {
      if (ct.includes("application/json")) {
        data = await request.json();
      } else {
        const fd = await request.formData();
        for (const [k, v] of fd.entries()) data[k] = v;
      }
    } catch (e) {
      return new Response(JSON.stringify({ ok: false, error: "Invalid body" }), {
        status: 400,
        headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
      });
    }

    // Honeypot anti-spam
    if (data._honeypot || data.website) {
      // Réponse OK silencieuse pour leurrer le bot
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
      });
    }

    const prenom = (data.prenom || "").toString().trim().substring(0, 100);
    const email = (data.email || "").toString().trim().substring(0, 200);
    const message = (data.message || "").toString().trim().substring(0, 5000);

    if (!isValidEmail(email)) {
      return new Response(JSON.stringify({ ok: false, error: "Email invalide" }), {
        status: 400,
        headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
      });
    }
    if (!message || message.length < 2) {
      return new Response(JSON.stringify({ ok: false, error: "Message requis" }), {
        status: 400,
        headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
      });
    }

    // Envoi parallèle des 2 emails
    const errors = [];
    try {
      await sendViaBrevo(env, buildNotificationEmail(env, { prenom, email, message }));
    } catch (e) {
      errors.push("notify:" + e.message);
    }
    try {
      await sendViaBrevo(env, buildAutoReplyEmail(env, { prenom, email }));
    } catch (e) {
      errors.push("autoreply:" + e.message);
    }

    if (errors.length === 2) {
      // Les deux ont échoué
      return new Response(JSON.stringify({ ok: false, error: errors.join(" | ") }), {
        status: 502,
        headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
      });
    }

    return new Response(JSON.stringify({ ok: true, warnings: errors }), {
      status: 200,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  },
};
