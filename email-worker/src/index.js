export default {
  async email(message, env, ctx) {
    // Forward the incoming email to both recipients
    const recipients = ["natquinson@gmail.com", "mimi.deco7@gmail.com"];
    for (const addr of recipients) {
      try {
        await message.forward(addr);
      } catch (e) {
        console.error(`Forward to ${addr} failed:`, e.message);
      }
    }
  },
};
