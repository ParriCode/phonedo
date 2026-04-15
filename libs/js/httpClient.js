const axios = require("axios");

function promiseGetRequest(url) {
    return new Promise((resolve, reject) => {
            console.log(url)
            axios.get(url)
                .then(res => {
                    resolve(res.data);
                })
                .catch(err => {
                    reject(err);
                });
        }
    )
}

function promisePostRequest(url, body) {
    return new Promise((resolve, reject) => {
            axios.post(url, body)
                .then(res => {
                    resolve(res.data);
                })
                .catch(err => {
                    reject(err);
                });
        }
    )
}

function promisePutRequest(url, body) {
    return new Promise((resolve, reject) => {
            axios.put(url, body)
                .then(res => {
                    resolve(res.data);
                })
                .catch(err => {
                    reject(err);
                });
        }
    )
}

function promiseDeleteRequest(url, body) {
    return new Promise((resolve, reject) => {
            axios.delete(url, { data: body })
                .then(res => {
                    resolve(res.data);
                })
                .catch(err => {
                    reject(err);
                });
        }
    )
}

module.exports = {promiseGetRequest, promisePostRequest, promiseDeleteRequest}