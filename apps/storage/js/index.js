const path = require("path");
require("dotenv").config({
  path: path.resolve(__dirname, "../config.env"),
});
const { Express } = require("@phonendo/http");
const { initDB, write, getAllItems, del, update } = require("./db.js");

async function start() {
    await initDB();

    const express = new Express(process.env.PORT_STORAGE, "Storage");



    express.get('/', async (_, res) => {
        let data = await getAllItems();
        res.json(data);
    });

    express.post('/devices', async (req, res) => {
        try {
            console.log("Device received: ", req.body);
            if (!req.body.token || req.body.token !== process.env.API_TOKEN_STORAGE) {
                return res.status(401).send('Not authorized');
            }

            if (!req.body.message) {
                return res.status(403).send("Bad request");
            }

            let message = req.body.message;
            console.log("Registro en db: ", message);
            await write(message.key, message.value);
            console.log("Device registered on db: " + message.key);
            return res.status(200).send("ok");
        } catch (error) {
            console.error(error);
            return res.status(500).send("Internal server error");
        }
    });

    express.post('/events', async (req, res) => {
        try {
            console.log("[STORAGE /events] Body:", req.body);

            if (!req.body.token || req.body.token !== process.env.API_TOKEN_STORAGE) {
                return res.status(401).send('Not authorized');
            }

            if (!req.body.message) {
                return res.status(403).send("Bad request");
            }

            const message = req.body.message;

            await write(message.key, message.value);

            console.log("[STORAGE /events] Stored:", message.key);

            return res.status(200).send("ok");

        } catch (error) {
            console.error("[STORAGE /events] Error:", error);
            return res.status(500).send("Internal server error");
        }
    });
    express.get('/raw', async (_, res) => {
        try {
            const data = await getAllItems();
            res.json(data);
        } catch (error) {
            console.error(error);
            res.status(500).send("Internal server error");
        }
    });
    express.run();
}

start().catch(console.error);