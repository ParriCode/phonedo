const { Express } = require("./Express");
const {
  promiseGetRequest,
  promisePostRequest,
  promisePutRequest,
  promiseDeleteRequest,
} = require("./httpClient");

module.exports = {
  Express,
  promiseGetRequest,
  promisePostRequest,
  promisePutRequest,
  promiseDeleteRequest,
};