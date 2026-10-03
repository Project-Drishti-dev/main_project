"""The question a summary is asked, and the self-hosted model that answers it.

``Summarizer`` is the interface every narration goes through, so a caller never
names a model.  ``LocalLLMClient`` speaks the one HTTP endpoint Ollama and
llama.cpp's server both serve, spends one budget on the whole exchange, and
answers ``None`` rather than raising: a local model that is absent, slow or
broken is an ordinary outcome, and 17.5's template is what the officer reads.
It is not called at all while ``LOCAL_LLM_ENABLED`` is off (17.8), which is
the state ``.env.example`` ships.
"""

import abc
import http.client
import json
import socket
import time
from urllib.parse import urlsplit

from app import config

__all__ = ["Summarizer", "LocalLLMClient", "GENERATE_PATH", "TEMPERATURE"]

#: The path both servers serve.  Ollama's own ``/api/generate`` and llama.cpp's
#: ``/completion`` are two native APIs and neither server answers the other's,
#: so the endpoint a client aimed at both has to be the one they share.
GENERATE_PATH = "/v1/chat/completions"

#: The narration is prose about flags the code has already decided, so it is
#: asked for cold: the same flags should not be narrated two different ways.
TEMPERATURE = 0

#: How much of a body is read at a time, so the budget can be re-imposed
#: between reads instead of being spent by one blocking read.
_CHUNK = 65_536


class Summarizer(abc.ABC):
    """The one question a summary is asked, and the shape of its answer.

    **``model_name`` belongs to the interface rather than to the client that
    answers**, so whatever wrote the text travels with it and a response can
    later name the model behind it (17.11).  A subclass that omits
    ``summarize`` cannot be instantiated, so a summariser wired wrongly fails
    at construction rather than on the first document.
    """

    #: What produced this summariser's answers, or ``None`` when no model is
    #: configured to answer.
    model_name: str | None

    @abc.abstractmethod
    def summarize(self, prompt: str) -> str | None:
        """The prose written from ``prompt``, or ``None`` when there is none.

        :param prompt: the prompt already assembled from the flag data.
        :returns: the model's own text, or ``None``.  ``None`` is the whole of
            the failure contract -- nothing here raises, because the caller
            has 17.5's template summary to fall back on.
        """
        raise NotImplementedError


class LocalLLMClient(Summarizer):
    """The self-hosted client: one address, one request, one budget.

    **There is no second address to try.**  The base URL is read once, the
    exchange is spent against it, and a failure answers ``None`` rather than a
    retry -- so nothing a prompt carries can leave the host the operator
    configured.  ``LOCAL_LLM_ENABLED`` gates the whole method, so the answer to
    "does anything leave this host" is "nothing" without reading a single
    character of the prompt.  Each ``None`` here is a value the caller acts on,
    which is why every failure below is caught rather than raised.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        """Take the configuration, or read it from :mod:`app.config` when absent.

        :param base_url: the local server's address; ``None`` reads
            :func:`app.config.get_local_llm_base_url`.
        :param model: the model to ask for; ``None`` reads
            :func:`app.config.get_local_llm_model`, which is itself ``None``
            when no model is configured -- the shipped state, and a client that
            answers ``None`` to everything.
        :param timeout: the budget in seconds; ``None`` reads
            :func:`app.config.get_local_llm_timeout_seconds`.

        **There is deliberately no argument for the master switch.**  The
        other three are tuning values a caller may override for a test, but a
        switch that a constructor could turn back on would not be one: this is
        the only reader of ``LOCAL_LLM_ENABLED``, so a deployment that has not
        asked for the model cannot be talked into calling it.
        """
        self._enabled = config.get_local_llm_enabled()
        self._base_url = (
            config.get_local_llm_base_url() if base_url is None else base_url
        )
        self._timeout = (
            config.get_local_llm_timeout_seconds() if timeout is None else timeout
        )
        self.model_name = config.get_local_llm_model() if model is None else model

    def summarize(self, prompt: str) -> str | None:
        """The prose ``prompt`` draws from the local model, or ``None``.

        The whole exchange shares one budget: the connect, the request, the
        status line and the body each get what is left of it, and a body that
        dribbles in past the budget is abandoned mid-read rather than waited
        out.  :returns: the model's text stripped of surrounding whitespace,
        or ``None`` for a switch that is off, a missing model, a blank
        prompt, an address that names no server, a refused connection, a body
        that outlived the budget, a status that is not ``200``, and a payload
        carrying no text.  Nothing raises, and nothing dials while the switch
        is off.
        """
        if not self._enabled:
            return None

        budget = _budget(self._timeout)
        target = _target(self._base_url)
        asked = _prompt(prompt)
        if not self.model_name or budget is None or target is None or asked is None:
            return None

        deadline = time.monotonic() + budget
        response = None
        sock = None
        try:
            sock = _dial(target[0], target[1], budget, deadline)
            sock.sendall(_request(self.model_name, asked, target))
            response = http.client.HTTPResponse(sock)
            response.begin()
            if response.status != 200:
                return None
            payload = json.loads(_read(sock, response, deadline).decode("utf-8"))
        except (
            OSError,
            http.client.HTTPException,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
        ):
            return None
        finally:
            _close(response, sock)
        return _content(payload)


def _budget(timeout: object) -> float | None:
    """``timeout`` as a positive number of seconds, or ``None`` when it is not one."""
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        return None
    return float(timeout) if timeout > 0 else None


def _prompt(prompt: object) -> str | None:
    """``prompt`` when it is text with something in it, else ``None``."""
    if not isinstance(prompt, str):
        return None
    return prompt if prompt.strip() else None


def _target(base_url: object) -> tuple[str, int, str] | None:
    """``(host, port, path)`` for ``base_url``, or ``None`` when it names no server.

    A URL naming anything else is refused here rather than refused by the
    socket, so a misconfigured deployment answers ``None`` to every request
    instead of dialling a host nobody meant to name.
    """
    if not isinstance(base_url, str) or not base_url.strip():
        return None
    try:
        parts = urlsplit(base_url.strip())
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        return None
    if parts.scheme not in config.SUPPORTED_LOCAL_LLM_SCHEMES or not parts.hostname:
        return None
    return parts.hostname, port, parts.path.rstrip("/") + GENERATE_PATH


def _body(model: str, prompt: str) -> bytes:
    """One non-streaming chat request as UTF-8 JSON bytes.

    UTF-8 rather than the latin-1 an HTTP body defaults to: a prompt quoting a
    document field can carry any character, and a mangled one would be sent on
    silently.
    """
    return json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "temperature": TEMPERATURE,
        }
    ).encode("utf-8")


def _dial(host: str, port: int, budget: float, deadline: float) -> socket.socket:
    """The socket to ``host``, holding what is left of the budget rather than all of it.

    **The exchange is run on a socket this module owns rather than through an
    ``HTTPConnection``**, for one reason: a response that ends the connection
    closes the socket out from under the client, and a socket that has been
    closed answers ``settimeout`` with ``OSError`` -- so the one place the
    budget is re-imposed would stop working exactly when a slow body starts.
    Nothing here but this function and :func:`_close` touches the socket.
    """
    sock = socket.create_connection((host, port), timeout=budget)
    _tighten(sock, deadline)
    return sock


def _request(model: str, prompt: str, target: tuple[str, int, str]) -> bytes:
    """One POST to ``target`` carrying the chat completion request as bytes.

    ``Connection: close`` because nothing here reuses the socket: it makes a
    reply that carries no length unambiguous, ending at the server's close
    rather than at the budget.
    """
    body = _body(model, prompt)
    head = (
        "POST {path} HTTP/1.1\r\n"
        "Host: {host}:{port}\r\n"
        "Content-Type: application/json\r\n"
        "Accept: application/json\r\n"
        "Content-Length: {length}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).format(path=target[2], host=target[0], port=target[1], length=len(body))
    return head.encode("ascii") + body


def _tighten(sock: socket.socket, deadline: float) -> None:
    """Hold the socket to what is left of the budget rather than to all of it."""
    sock.settimeout(max(0.0, deadline - time.monotonic()))


def _read(sock: socket.socket, response: object, deadline: float) -> bytes:
    """The whole body, read in chunks the budget is re-imposed between.

    One blocking read would be bounded by the socket timeout but not by the
    remaining budget, so a server dribbling bytes keeps the client waiting for
    one window after another.  Re-imposing the deadline before every chunk is
    what makes the budget a total for the body rather than a per-read.
    """
    chunks: list[bytes] = []
    while True:
        _tighten(sock, deadline)
        chunk = response.read(_CHUNK)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _content(payload: object) -> str | None:
    """The text one chat completion carries, or ``None`` when it carries none."""
    try:
        text = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    return text.strip() if isinstance(text, str) and text.strip() else None


def _close(response: object, sock: object) -> None:
    """Let go of the response and the socket, and let nothing here escape."""
    for closeable in (response, sock):
        if closeable is None:
            continue
        try:
            closeable.close()
        except OSError:
            pass


