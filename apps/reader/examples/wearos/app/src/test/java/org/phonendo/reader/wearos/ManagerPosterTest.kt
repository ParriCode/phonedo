// Envío a los Managers: la lista de URLs como la del ESP32, el cuerpo de
// /newEvent como {**sobre, "token": ...} en manager_output.py, y un Manager
// colgado que no retrasa a los demás.
package org.phonendo.reader.wearos

import java.util.concurrent.CountDownLatch
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ManagerPosterTest {
    @Test
    fun parsesCommaSeparatedUrls() {
        assertEquals(
            listOf("http://a:3003", "http://b"),
            ManagerPoster.parseUrls(" http://a:3003/ , ,http://b ")
        )
        assertEquals(emptyList<String>(), ManagerPoster.parseUrls(""))
    }

    @Test
    fun bodyIsTheEnvelopePlusToken() {
        val envelope = "{\"eventType\":\"observation\",\"payload\":{\"unit\":\"bpm\"}}"
        assertEquals(
            "{\"eventType\":\"observation\",\"payload\":{\"unit\":\"bpm\"},\"token\":\"t\\\"k\"}",
            ManagerPoster.newEventBody(envelope, "t\"k")
        )
        assertEquals(
            "{\"eventType\":\"observation\",\"token\":\"\"}",
            ManagerPoster.newEventBody("{\"eventType\":\"observation\"}", "")
        )
    }

    @Test
    fun postsToNewEventOfEveryManager() {
        val calls = LinkedBlockingQueue<Pair<String, String>>()
        val results = LinkedBlockingQueue<PostResult>()
        val poster = ManagerPoster(listOf("http://a", "http://b"), "tk", { url, body ->
            calls += url to body
            204
        }, { results += it })
        poster.post("{\"eventType\":\"observation\"}")
        val first = results.poll(5, TimeUnit.SECONDS)
        val second = results.poll(5, TimeUnit.SECONDS)
        poster.shutdown()
        assertNotNull(first)
        assertNotNull(second)
        assertTrue(first!!.ok && second!!.ok)
        assertEquals(
            setOf("http://a/newEvent", "http://b/newEvent"),
            calls.map { it.first }.toSet()
        )
        assertTrue(calls.all { it.second == "{\"eventType\":\"observation\",\"token\":\"tk\"}" })
    }

    @Test
    fun aHungManagerDoesNotBlockTheOthers() {
        val release = CountDownLatch(1)
        val results = LinkedBlockingQueue<PostResult>()
        val poster = ManagerPoster(listOf("http://colgado", "http://vivo"), "", { url, _ ->
            if (url.startsWith("http://colgado")) release.await(10, TimeUnit.SECONDS)
            200
        }, { results += it })
        poster.post("{}")
        val first = results.poll(5, TimeUnit.SECONDS)
        release.countDown()
        poster.shutdown()
        assertEquals("http://vivo/newEvent", first?.url)
    }

    @Test
    fun failuresAreReportedNotThrown() {
        val results = LinkedBlockingQueue<PostResult>()
        val poster = ManagerPoster(listOf("http://a"), "", { _, _ -> throw java.io.IOException("sin red") }, { results += it })
        poster.post("{}")
        val result = results.poll(5, TimeUnit.SECONDS)
        poster.shutdown()
        assertNotNull(result)
        assertFalse(result!!.ok)
        assertEquals("sin red", result.error)

        val rejected = PostResult("http://a/newEvent", 500, null)
        assertFalse(rejected.ok)
    }
}
