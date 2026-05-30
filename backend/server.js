import express from "express";
import path from "path";
import { fileURLToPath } from "url";
import { sequelize, dbKind } from "./db.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = process.env.PORT || 3001;

app.use(express.json());

app.get("/api/health", async (req, res) => {
  try {
    await sequelize.authenticate();
    res.json({ status: "ok", db: dbKind });
  } catch (err) {
    res.status(500).json({ status: "error", message: err.message });
  }
});

app.get("/api/hello", (req, res) => {
  res.json({ message: "Hello from the backend 👋" });
});

if (process.env.NODE_ENV === "production") {
  app.use(express.static(path.join(__dirname, "public")));
  app.get("*", (req, res) => {
    res.sendFile(path.join(__dirname, "public", "index.html"));
  });
}

app.listen(PORT, () => {
  console.log(`Server listening on port ${PORT} (db: ${dbKind})`);
});
