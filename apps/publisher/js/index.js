const path = require("path");
require("dotenv").config({
  path: path.resolve(__dirname, "../config.env"),
});
const { Express } = require("@phonendo/http");
const { ClientBuilder } = require('@iota/client');
var lastMessageId = "";

const client = new ClientBuilder()
    //Para que deje de dar errores el cabroncete
    //.node('https://api.lb-0.h.chrysalis-devnet.iota.cafe')
    .build();

const express = new Express(process.env.PORT_PUBLISHER, "Publisher")
express.get('/', (_, res) => {
    client.getInfo().then(console.log).catch(console.error);
    res.send('Service is alive')
});

express.post('/publish', async (req, res) => {
    if (!req.body.token || req.body.token !== process.env.API_TOKEN_PUBLISHER) {
        res.status(401).send('Not authorized');
    } else {
        if (!req.body.message) {
            res.status(403).send("Bad request");
        } else {
            console.log(lastMessageId)
            let iotaBuilder = client.message()
                .index('PHONENDO')
                .data(JSON.stringify(req.body.message));

            if (lastMessageId) {
                iotaBuilder.parents([lastMessageId])
            }

            const iotaMessage = await iotaBuilder.submit();

            lastMessageId = iotaMessage.messageId;
            console.log("Event published on IOTA" + JSON.stringify(iotaMessage));
            res.status(200).send(req.body.message);
        }
    }
});

express.run();