const express = require("express");
const bodyParser = require('body-parser');

class Express {
  #app;
  #name;
  #port;

  constructor(port, name = "Service") {
    this.#app = express();
    this.#app.use(bodyParser.json());
    this.#app.use(bodyParser.urlencoded({ extended: true }));
    this.#name = name;
    this.#port = port;
  }

  get app() {
    return this.#app;
  }

  get = (path, f) => this.#app.get(path, f);
  post = (path, f) => this.#app.post(path, f);
  put = (path, f) => this.#app.put(path, f);
  delete = (path, f) => this.#app.delete(path, f);

  run = () => {
    this.#app.listen(this.#port, () =>
        console.log(`${this.#name} listening on port ${this.#port}`)
    );
  }
}

module.exports.Express = Express;
