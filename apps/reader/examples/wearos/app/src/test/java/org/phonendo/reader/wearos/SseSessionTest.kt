// La sesión SSE de cada cliente: ": connected" al abrir, los eventos en orden,
// ": heartbeat" tras 15 s sin escribir y "stream_closed" al cerrar; siempre se
// da de baja del stream al terminar.
package org.phonendo.reader.wearos

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SseSessionTest {
    private class FakeStream : StreamPort {
        val frames = ArrayDeque<StreamFrame>()
        val unsubscribed = mutableListOf<Int>()
        override val connectedFrame = ": connected\n\n"
        override val heartbeatFrame = ": heartbeat\n\n"
        override fun subscribe() = 7
        override fun unsubscribe(id: Int) {
            unsubscribed += id
        }
        override fun poll(id: Int): StreamFrame? = frames.removeFirstOrNull()
    }

    private var now = 1_000L
    private val written = mutableListOf<String>()
    private var writable = true
    private val stream = FakeStream()
    private val session = SseSession(stream, 7, { written += it; writable }, { now })

    @Test
    fun opensWithConnectedComment() {
        assertTrue(session.open())
        assertEquals(listOf(": connected\n\n"), written)
    }

    @Test
    fun writesEventsInOrder() {
        session.open()
        stream.frames += StreamFrame.Event("event: observation\ndata: {\"n\":1}\n\n")
        stream.frames += StreamFrame.Event("event: observation\ndata: {\"n\":2}\n\n")
        assertTrue(session.step())
        assertEquals(
            listOf(": connected\n\n", "event: observation\ndata: {\"n\":1}\n\n", "event: observation\ndata: {\"n\":2}\n\n"),
            written
        )
    }

    @Test
    fun heartbeatOnlyAfterFifteenIdleSeconds() {
        session.open()
        now += 14_999
        assertTrue(session.step())
        assertEquals(1, written.size)
        now += 1
        assertTrue(session.step())
        assertEquals(": heartbeat\n\n", written.last())
        now += 10_000
        assertTrue(session.step())
        assertEquals(2, written.size)
    }

    @Test
    fun eventsPostponeTheHeartbeat() {
        session.open()
        now += 10_000
        stream.frames += StreamFrame.Event("event: observation\ndata: {}\n\n")
        session.step()
        now += 10_000
        session.step()
        assertFalse(written.contains(": heartbeat\n\n"))
    }

    @Test
    fun closedFrameEndsTheSession() {
        session.open()
        stream.frames += StreamFrame.Closed("event: stream_closed\ndata: {}\n\n")
        assertFalse(session.step())
        assertEquals("event: stream_closed\ndata: {}\n\n", written.last())
        session.finish()
        assertEquals(listOf(7), stream.unsubscribed)
    }

    @Test
    fun failedWriteEndsTheSession() {
        session.open()
        writable = false
        stream.frames += StreamFrame.Event("event: observation\ndata: {}\n\n")
        assertFalse(session.step())
        session.finish()
        session.finish()
        assertEquals(listOf(7), stream.unsubscribed)
    }
}
