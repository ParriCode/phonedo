const { Level } = require("level");

const db = new Level("/tmp/phonendo_db_final", { valueEncoding: "json" });



async function initDB() {
  await db.open();
}

const write = async (key, value) => {
  try {
    await db.get(key);
  } catch (error) {
    await db.put(key, value);
  }
};

const read = async (key) => {
  let result = "";
  try {
    result = await db.get(key);
  } catch (error) {
    console.warn(`DB ${key} not found`);
  }
  return result;
};

const update = async (key, value) => {
  await del(key);
  await write(key, value);
};

const del = async (key) => {
  let result = "";
  try {
    result = await db.del(key);
  } catch (error) {
    console.warn(`DB ${key} not found`);
  }
};

const getAllCapturedItems = async () => {

  let capturedItems = [];

  try {
    for await (const data of db.iterator()) {
      const [key, value] = data;
      if (value.status === "Captured") {
        capturedItems.push(data);
      }
    }

    return capturedItems;
  } catch (err) {
    console.error(err)

    return capturedItems;
  }
};

const getAllItems = async () => {

  let capturedItems = [];

  try {
    for await (const data of db.iterator()) {
      const [key, value] = data;
      capturedItems.push(data);
    }

    return capturedItems;
  } catch (err) {
    console.error(err)

    return capturedItems;
  }
};

module.exports = { initDB, write, read, update, del, getAllCapturedItems, getAllItems };
