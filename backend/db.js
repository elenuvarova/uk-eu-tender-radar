// The dialect is picked from DATABASE_URL so the same config works locally
// (no DATABASE_URL → SQLite file) and on Render (DATABASE_URL → Postgres).
import { Sequelize } from "sequelize";

const url = process.env.DATABASE_URL;
const isPostgres =
  typeof url === "string" &&
  (url.startsWith("postgres://") || url.startsWith("postgresql://"));

export const dbKind = isPostgres ? "postgres" : "sqlite";

export const sequelize = isPostgres
  ? new Sequelize(url, {
      dialect: "postgres",
      logging: false,
      dialectOptions:
        process.env.NODE_ENV === "production"
          ? { ssl: { require: true, rejectUnauthorized: false } }
          : {},
    })
  : new Sequelize({
      dialect: "sqlite",
      storage: process.env.SQLITE_PATH || "./data.sqlite",
      logging: false,
    });
