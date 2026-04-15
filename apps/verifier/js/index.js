require('dotenv').config()
const {Express} = require("@phonendo/http");
const path = require("path");
const { createSign, createPrivateKey, createPublicKey, generateKeyPairSync } = require("node:crypto");

// Import keys
const fs = require('fs');
let keys = JSON.parse(fs.readFileSync(path.resolve(__dirname, "../keys.json"), "utf8")
);privateKey = createPrivateKey({
    key: keys.privateKey,
    type: "pkcs8",
    format: "pem",
});

const express = new Express(process.env.PORT_VERIFIER, "Verifier")
express.get('/', (_, res) => {
    res.send('Service is alive')
});

express.post('/verify', (req, res) => {

    if (!req.body.token || req.body.token !== process.env.API_TOKEN_VERIFIER) {
        res.status(401).send('Not authorized');
    } else {
        if (!req.body.message) {
            res.status(403).send("Bad request");
        } else {
            let message = req.body.message;

            const sign = createSign("SHA256");
            sign.write(JSON.stringify(message));
            sign.end();
            const signature = sign.sign(privateKey, "hex");
            message.value.verifierSign = signature;
            message.value.verifierSignDatetime = new Date().getTime();

            console.log("Event Verified with signature: " + signature);
            res.status(200).send(message);
        }
    }
});
express.run();