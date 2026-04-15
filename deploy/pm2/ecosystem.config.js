const path = require("path");

const ROOT = path.resolve(__dirname, "../..");

module.exports = {
  apps: [
    {
      name: "manager",
      cwd: path.join(ROOT, "apps/manager/js"),
      script: "index.js",
      watch: true,
      env: {
        PORT_MANAGER: 3003,
        API_TOKEN_MANAGER: "token_manager",
        API_TOKEN_STORAGE: "token_storage",
        INTERNAL_URL_STORAGE_DEVICES: "http://localhost:3005/devices",
        INTERNAL_URL_STORAGE_EVENTS: "http://localhost:3005/events",
        API_TOKEN_VERIFIER: "token_verifier",
        INTERNAL_URL_VERIFIER_VERIFY: "http://localhost:3004/verify",
        API_TOKEN_PUBLISHER: "token_publisher",
        INTERNAL_URL_PUBLISHER_PUBLISH: "http://localhost:3006/publish"
      }
    },
    {
      name: "verifier",
      cwd: path.join(ROOT, "apps/verifier/js"),
      script: "index.js",
      watch: true,
      env: {
        PORT_VERIFIER: 3004,
        API_TOKEN_VERIFIER: "token_verifier"
      }
    },
    {
      name: "storage",
      cwd: path.join(ROOT, "apps/storage/js"),
      script: "index.js",
      ignore_watch: ["phonendo_db", "phonendo_db_test", "phonendo_db_v3"],
      watch: false,
      env: {
        PORT_STORAGE: 3005,
        API_TOKEN_STORAGE: "token_storage"
      }
    },
    {
      name: "reader",
      cwd: path.join(ROOT, "apps/reader/js"),
      script: "index.js",
      watch: true,
      env: {
        PORT_READER: 3002,
        API_TOKEN_MANAGER: "token_manager",
        INTERNAL_URL_MANAGER_REGISTER_DEVICE: "http://localhost:3003/registerDevice",
        INTERNAL_URL_MANAGER_NEW_EVENT: "http://localhost:3003/newEvent"
      }
    },
    {
      name: "publisher",
      cwd: path.join(ROOT, "apps/publisher/js"),
      script: "index.js",
      watch: true,
      env: {
        PORT_PUBLISHER: 3006,
        API_TOKEN_PUBLISHER: "token_publisher"
      }
    }
  ]
};