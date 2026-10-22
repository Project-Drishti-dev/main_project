"""17.7 -- the Summarizer interface and the self-hosted client behind it.

The client's whole contract is what it answers when the model is not there.  A
local server that is absent, slow, broken, silent or dribbling must come back
as ``None`` inside its budget, because 17.5's template is what the officer
reads then and nothing here may raise into a screening.

Every case runs against a stub on loopback or a port nothing is listening on,
so each request the client makes is one this file can see, count and read back.
That is what pins the two claims a unit test would otherwise take on trust:
that the budget is a total for the exchange rather than per read, and that a
failure is answered rather than retried somewhere else.
"""

import ast
import contextlib
import http.server
import json
import pathlib
import socket
import threading
import time
from urllib.parse import urlsplit

import pytest

from app import config
from app.explain import summarizer

#: How often a stub checks whether it has been asked to stop.  The default half
#: second is paid by every stub that stops, and this file starts twenty.
_POLL = {"poll_interval": 0.05}

MODEL = "drishti-narrator"
PROMPT = "Narrate these flags: DATE_EXPIRED, FACE_MISMATCH."
ANSWER = "This document reads as high risk."
TIMEOUT = 2

#: One completion in the shape Ollama and llama.cpp's server both answer, and a
#: payload per way of carrying no text in it.
COMPLETION = json.dumps(
    {"choices": [{"message": {"role": "assistant", "content": "  " + ANSWER + "  "}}]}
).encode("utf-8")
NO_TEXT = (
    b"{}",
    b'{"choices": []}',
    b'{"choices": [{"message": {}}]}',
    b'{"choices": [{"message": {"content": ""}}]}',
    b'{"choices": [{"message": {"content": "   "}}]}',
    b'{"choices": [{"message": {"content": 5}}]}',
    b'{"choices": [{"message": "text"}]}',
    b'{"choices": "not a list"}',
    b"[]",
    b"null",
)


@pytest.fixture(autouse=True)
def _no_configured_local_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every case starts from a known configuration, whatever the shell carries.

    The three 17.7 variables are unset, which is what ``.env.example`` ships.
    The 17.8 switch is the exception: it is *on* here so the cases below reach
    the client at all, and the cases that are about it being off set it back.
    """
    for name in (
        config.LOCAL_LLM_BASE_URL_ENV_VAR,
        config.LOCAL_LLM_MODEL_ENV_VAR,
        config.LOCAL_LLM_TIMEOUT_ENV_VAR,
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(config.LOCAL_LLM_ENABLED_ENV_VAR, "true")


def _client(base_url: object, **overrides: object) -> summarizer.LocalLLMClient:
    """A client aimed at ``base_url``, asking for :data:`MODEL`."""
    arguments = {"base_url": base_url, "model": MODEL, "timeout": TIMEOUT}
    arguments.update(overrides)
    return summarizer.LocalLLMClient(**arguments)


def _closed_port() -> int:
    """A loopback port nothing is listening on, released the moment it is known."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@contextlib.contextmanager
def _answering(body: bytes, *, status: int = 200, delay: float = 0.0):
    """A loopback stub recording what arrived, answering ``body`` after ``delay``."""
    received: list[tuple[str, object, bytes]] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            received.append((self.requestline, dict(self.headers), self.rfile.read(length)))
            if delay:
                time.sleep(delay)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            """A stub is not a service, and its request log is noise."""

    with _serving(Handler) as url:
        yield url, received


@contextlib.contextmanager
def _dribbling(parts: int, gap: float, size: int):
    """A loopback stub sending one body ``parts`` times, ``gap`` apart.

    No ``Content-Length`` is sent and the connection is HTTP/1.0, so the client
    is reading a body of unknown length until the server hangs up -- which is
    what a server too slow to finish looks like from the other end.
    """
    received: list[tuple[str, object, bytes]] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            received.append((self.requestline, dict(self.headers), self.rfile.read(length)))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            for _ in range(parts):
                self.wfile.write(b" " * size)
                self.wfile.flush()
                time.sleep(gap)
            self.close_connection = True

        def log_message(self, *args: object) -> None:
            """A stub is not a service, and its request log is noise."""

    with _serving(Handler) as url:
        yield url, received


@contextlib.contextmanager
def _serving(handler: type):
    """Run ``handler`` on loopback for the life of the block, on daemon threads.

    Daemon threads matter for the slow cases: a stub still sleeping after the
    client has given up must not hold the suite open until it wakes.
    """
    class Server(http.server.ThreadingHTTPServer):
        daemon_threads = True

        def handle_error(self, request: object, client_address: object) -> None:
            """A stub whose client gave up is the case under test, not noise."""

    server = Server(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, kwargs=_POLL, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_a_non_existent_endpoint_answers_none_inside_the_timeout() -> None:
    """The task's own case: nothing is listening, and the answer is ``None``.

    Measured against the budget rather than assumed beneath it.  A host that
    refuses a closed loopback port answers in milliseconds; one that drops the
    connection instead -- which is what this host does, measured -- spends the
    budget first and is answered by the timeout.  Either way the call ends no
    later than its budget, which is the claim: an unbounded client here would
    hang until the operating system gave up dialling.
    """
    client = _client(f"http://127.0.0.1:{_closed_port()}")

    started = time.monotonic()
    answer = client.summarize(PROMPT)
    elapsed = time.monotonic() - started

    assert answer is None
    assert elapsed <= TIMEOUT + 1


def test_a_server_that_never_answers_is_abandoned_inside_the_budget() -> None:
    """A model that is loaded but thinking is a timeout, not a refusal.

    The stub would take thirty seconds to reply and the budget is one, so
    ``None`` here can only have come from the budget being spent.
    """
    with _answering(COMPLETION, delay=30) as (url, _received):
        started = time.monotonic()
        answer = _client(url, timeout=1).summarize(PROMPT)
        elapsed = time.monotonic() - started

    assert answer is None
    assert elapsed < 5


def test_a_body_arriving_after_the_budget_is_abandoned_mid_read() -> None:
    """The budget is a total for the exchange, not a fresh one per read.

    The stub sends four large pieces a second apart, so a client that re-imposed
    the whole budget before each read would take the last piece and succeed at
    about 3.2 seconds.  Answering ``None`` by 2 is the budget being a deadline
    rather than an interval, and the request is recorded, so it is the body
    that was abandoned rather than a connection never made.
    """
    with _dribbling(parts=4, gap=0.8, size=100_000) as (url, received):
        started = time.monotonic()
        answer = _client(url, timeout=1).summarize(PROMPT)
        elapsed = time.monotonic() - started

    assert answer is None
    assert elapsed < 2
    assert len(received[0][2]) > 0


def test_the_models_text_is_returned_stripped() -> None:
    """The one answer that is not ``None``: what the local model wrote."""
    with _answering(COMPLETION) as (url, _received):
        assert _client(url).summarize(PROMPT) == ANSWER


def test_the_request_is_one_non_streaming_chat_completion() -> None:
    """The wire shape, read back off the stub rather than asserted in the abstract.

    ``stream`` is what makes the reply one JSON body instead of a line per
    token, and the model name is the one 17.7 is configured with rather than
    one the client invented.
    """
    with _answering(COMPLETION) as (url, received):
        assert _client(url).summarize(PROMPT) == ANSWER

    (requestline, headers, body), = received
    sent = json.loads(body.decode("utf-8"))
    assert requestline == "POST /v1/chat/completions HTTP/1.1"
    assert requestline.split()[1] == summarizer.GENERATE_PATH
    assert headers["Content-Type"] == "application/json"
    assert headers["Connection"] == "close"
    assert headers["Content-Length"] == str(len(body))
    assert sent["model"] == MODEL
    assert sent["messages"] == [{"role": "user", "content": PROMPT}]
    assert sent["stream"] is False
    assert sent["temperature"] == summarizer.TEMPERATURE


@pytest.mark.parametrize("character", ["é", "न", "—", "\n"])
def test_a_prompt_is_sent_as_utf8_and_arrives_intact(character: str) -> None:
    """``http.client`` encodes a text body as latin-1, which mangles a prompt.

    A document field can carry any character, so the request is built as UTF-8
    bytes and this pins that it survives the trip rather than being silently
    corrupted on the way out.
    """
    prompt = PROMPT + " " + character
    with _answering(COMPLETION) as (url, received):
        _client(url).summarize(prompt)

    assert json.loads(received[0][2].decode("utf-8"))["messages"][0]["content"] == prompt


@pytest.mark.parametrize("status", [400, 404, 500, 503])
def test_a_status_that_is_not_200_answers_none(status: int) -> None:
    """A server that refused the request has said no, and no is ``None``."""
    with _answering(COMPLETION, status=status) as (url, _received):
        assert _client(url).summarize(PROMPT) is None


def test_a_failure_is_answered_where_it_happened_and_never_retried() -> None:
    """No external fallback: one request, one address, no second attempt.

    A client that fell back to a hosted API on failure would have no record on
    this stub to count, so the count is the pin -- one request arrived and the
    answer was ``None``, so the prompt went nowhere else either.
    """
    with _answering(COMPLETION, status=500) as (url, received):
        assert _client(url).summarize(PROMPT) is None

    assert len(received) == 1


def test_the_client_module_names_no_host_of_its_own() -> None:
    """The static half of the same claim: there is no second address to fall
    back to, because the module holds no URL at all.

    Read off the source rather than the behaviour, so it survives a fallback
    added to a path this file does not happen to exercise.
    """
    source = pathlib.Path(summarizer.__file__).read_text(encoding="utf-8")

    assert "http://" not in source
    assert "https://" not in source


def test_the_client_module_reaches_the_network_only_through_the_standard_library() -> None:
    """An HTTP client that could call a hosted API would do it through some
    library; pinning the imports keeps that a decision rather than a default."""
    tree = ast.parse(pathlib.Path(summarizer.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")

    assert imported <= {
        "abc",
        "app",
        "http.client",
        "json",
        "socket",
        "time",
        "urllib.parse",
    }


@pytest.mark.parametrize("body", [b"", b"not json", b"{", b'{"choices": [{"message"'])
def test_a_body_that_is_not_a_completion_answers_none(body: bytes) -> None:
    """A truncated or non-JSON reply is a broken server, and broken is ``None``."""
    with _answering(body) as (url, _received):
        assert _client(url).summarize(PROMPT) is None


@pytest.mark.parametrize("payload", NO_TEXT)
def test_a_payload_carrying_no_text_answers_none(payload: bytes) -> None:
    """A well-formed reply that holds no prose is no summary.

    Every shape here is a ``200`` carrying JSON, so nothing may read them as a
    refusal except the answer to whether there is text in them.
    """
    with _answering(payload) as (url, _received):
        assert _client(url).summarize(PROMPT) is None


@pytest.mark.parametrize(
    "prompt", ["", "   ", "\n\t ", None, 42, ["a prompt"], {"prompt": "x"}]
)
def test_a_prompt_with_nothing_to_say_answers_none_and_dials_nobody(prompt: object) -> None:
    """The client asks nothing and sends nothing.

    Recorded on the stub as well as on the return value: a client that dialled
    first and checked the prompt afterwards would answer ``None`` all the same.
    """
    with _answering(COMPLETION) as (url, received):
        assert _client(url).summarize(prompt) is None

    assert received == []


def test_a_client_with_no_model_named_answers_none_and_dials_nobody() -> None:
    """``LOCAL_LLM_MODEL`` blank is what ``.env.example`` ships."""
    with _answering(COMPLETION) as (url, received):
        assert _client(url, model=None).summarize(PROMPT) is None

    assert received == []


@pytest.mark.parametrize(
    "base_url",
    ["", "   ", "not a url", "ollama://127.0.0.1:11434", "http://", "http://:11434"],
)
def test_an_address_naming_no_server_answers_none_and_dials_nobody(base_url: object) -> None:
    """A base URL the client cannot turn into a host is refused before the
    connect, not by the socket.

    ``None`` here means the configuration is read, and a deployment pointed at
    an address nothing can answer stays pointed at it rather than dialling the
    default instead.
    """
    with _answering(COMPLETION) as (url, _received):
        assert _client(url if base_url is None else base_url).summarize(PROMPT) is None


@pytest.mark.parametrize("timeout", [0, -1, -0.5, "5", object(), True])
def test_a_budget_that_is_not_one_is_refused_before_the_connect(timeout: object) -> None:
    """Zero is not "no budget" and a string is not five seconds.

    Either would otherwise be spent inside ``HTTPConnection``, where the
    failure arrives as a socket error rather than as the configuration refusal
    it is.
    """
    with _answering(COMPLETION) as (url, received):
        assert _client(url, timeout=timeout).summarize(PROMPT) is None

    assert received == []


def test_a_timeout_read_from_the_configuration_is_the_one_spent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A client built with no timeout is the configured client.

    The budget is set through the environment rather than the argument so this
    covers the reader, and it is one second rather than the thirty the
    default is, because the stub this is answered by is one that never replies.
    """
    monkeypatch.setenv(config.LOCAL_LLM_TIMEOUT_ENV_VAR, "1")
    with _answering(COMPLETION, delay=30) as (url, _received):
        client = summarizer.LocalLLMClient(base_url=url, model=MODEL)
        started = time.monotonic()
        answer = client.summarize(PROMPT)
        elapsed = time.monotonic() - started

    assert answer is None
    assert elapsed < 5


def test_a_scheme_no_local_server_speaks_is_refused_where_the_host_would_answer() -> None:
    """The refusal is read off the address, not off the failure to dial.

    The host here is listening and would answer, so a client that merely failed
    to connect would answer ``None`` for the wrong reason.  Nothing arriving on
    the stub is what makes this the scheme being read.
    """
    with _answering(COMPLETION) as (url, received):
        assert _client(url.replace("http://", "ollama://")).summarize(PROMPT) is None

    assert received == []


def test_a_base_url_carrying_a_path_is_answered_under_that_path() -> None:
    """A server behind a prefix is reached under it.

    Ollama's own port serves the API at its root, but the same server behind a
    reverse proxy sits under one -- and dropping the configured prefix would
    turn a working deployment into a client dialling a path that answers 404.
    """
    with _answering(COMPLETION) as (url, received):
        assert _client(url + "/ollama").summarize(PROMPT) == ANSWER

    assert received[0][0].split()[1] == "/ollama" + summarizer.GENERATE_PATH


def test_the_default_address_is_loopback_and_the_default_budget_is_thirty_seconds() -> None:
    """What an unconfigured deployment gets, read as the values themselves."""
    assert config.get_local_llm_base_url() == "http://127.0.0.1:11434"
    assert config.get_local_llm_base_url().startswith("http://127.0.0.1:")
    assert config.get_local_llm_timeout_seconds() == 30
    assert config.get_local_llm_model() is None


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_a_model_that_is_not_named_is_no_model(blank: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The value ``.env.example`` ships, and the one a first run will have."""
    monkeypatch.setenv(config.LOCAL_LLM_MODEL_ENV_VAR, blank)

    assert config.get_local_llm_model() is None


def test_the_configured_model_is_read_as_written_and_trimmed(monkeypatch: pytest.MonkeyPatch) -> None:
    """What ``ollama list`` reports, with a shell's padding around it."""
    monkeypatch.setenv(config.LOCAL_LLM_MODEL_ENV_VAR, "  llama3.2:3b  ")

    assert config.get_local_llm_model() == "llama3.2:3b"


@pytest.mark.parametrize("written", [" 7 ", "7"])
def test_the_configured_budget_is_read_as_a_whole_number_of_seconds(written: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(config.LOCAL_LLM_TIMEOUT_ENV_VAR, written)

    assert config.get_local_llm_timeout_seconds() == 7


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_budget_is_the_default_budget(blank: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(config.LOCAL_LLM_TIMEOUT_ENV_VAR, blank)

    assert config.get_local_llm_timeout_seconds() == config.DEFAULT_LOCAL_LLM_TIMEOUT_SECONDS


@pytest.mark.parametrize(
    "refused",
    [
        "not a url",
        "ollama://127.0.0.1:11434",
        "127.0.0.1:11434",
        "http://",
        "http://127.0.0.1:0",
        "http://127.0.0.1:99999",
        "http://127.0.0.1:not-a-port",
    ],
)
def test_an_address_naming_no_server_is_refused_where_it_was_configured(refused: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Refused while the configuration is read, rather than at the first request.

    17.7 asks a failure to answer ``None``, and it does -- but a bad address is
    a deployment that will answer ``None`` to every document, which is worth a
    refusal at start-up naming the variable.
    """
    monkeypatch.setenv(config.LOCAL_LLM_BASE_URL_ENV_VAR, refused)

    with pytest.raises(ValueError) as refusal_error:
        config.get_local_llm_base_url()

    assert config.LOCAL_LLM_BASE_URL_ENV_VAR in str(refusal_error.value)


@pytest.mark.parametrize(
    "written,read",
    [
        ("http://127.0.0.1:11434/", "http://127.0.0.1:11434"),
        ("  http://192.168.1.10:11434  ", "http://192.168.1.10:11434"),
        ("https://models.internal:8443/", "https://models.internal:8443"),
    ],
)
def test_an_address_that_names_a_local_server_is_accepted_as_written(written: str, read: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Loopback, a LAN box and a TLS endpoint are all "a local model server".

    ``.env.example`` says the address may be a LAN address rather than
    loopback, so refusing one would refuse the deployment the project describes.
    A trailing slash is trimmed rather than refused: it names the same server.
    """
    monkeypatch.setenv(config.LOCAL_LLM_BASE_URL_ENV_VAR, written)

    assert config.get_local_llm_base_url() == read


@pytest.mark.parametrize(
    "written,target",
    [
        ("http://models.internal", ("models.internal", 80, "/v1/chat/completions")),
        ("https://models.internal", ("models.internal", 443, "/v1/chat/completions")),
        ("https://models.internal:8443/", ("models.internal", 8443, "/v1/chat/completions")),
        ("http://127.0.0.1:11434/ollama", ("127.0.0.1", 11434, "/ollama/v1/chat/completions")),
    ],
)
def test_the_address_the_client_dials_is_read_off_the_base_url(written: str, target: tuple) -> None:
    """Host, port and path, and where each of them comes from.

    The two default ports are the part that is not visible in the string, and a
    scheme that fell back to the other server's default would be refused by
    every local model behind TLS.
    """
    assert summarizer._target(written) == target


@pytest.mark.parametrize("refused", ["0", "-1", "-30", "1.5", "abc", "7s"])
def test_a_budget_that_is_not_a_whole_number_of_seconds_is_refused(refused: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Zero is refused rather than read as "no budget"."""
    monkeypatch.setenv(config.LOCAL_LLM_TIMEOUT_ENV_VAR, refused)

    with pytest.raises(ValueError) as refusal_error:
        config.get_local_llm_timeout_seconds()

    assert config.LOCAL_LLM_TIMEOUT_ENV_VAR in str(refusal_error.value)


def test_the_client_is_a_summarizer() -> None:
    """A caller names the interface and gets the client."""
    with _answering(COMPLETION) as (url, _received):
        assert isinstance(_client(url), summarizer.Summarizer)


def test_the_summarizer_interface_cannot_be_instantiated() -> None:
    """The interface is a question, not an answer."""
    with pytest.raises(TypeError):
        summarizer.Summarizer()


def test_a_summarizer_that_omits_the_question_cannot_be_instantiated() -> None:
    """A client wired wrongly fails at construction, not on the first document."""

    class HalfASummarizer(summarizer.Summarizer):
        model_name = "half"

    with pytest.raises(TypeError):
        HalfASummarizer()


def test_the_model_name_travels_with_the_client() -> None:
    """Whatever wrote the text has to be nameable, so it is on the interface."""

    class Answering(summarizer.Summarizer):
        model_name = "a-model"

        def summarize(self, prompt: str) -> str | None:
            return None

    assert Answering().model_name == "a-model"
    assert summarizer.LocalLLMClient(model=MODEL).model_name == MODEL
    assert summarizer.LocalLLMClient(model=None).model_name is None


def test_the_configured_address_is_read_when_none_is_passed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A client built with no arguments uses the configuration, not a default."""
    monkeypatch.setenv(config.LOCAL_LLM_BASE_URL_ENV_VAR, "http://127.0.0.1:9999/")
    monkeypatch.setenv(config.LOCAL_LLM_MODEL_ENV_VAR, MODEL)
    monkeypatch.setenv(config.LOCAL_LLM_TIMEOUT_ENV_VAR, "7")

    client = summarizer.LocalLLMClient()

    assert client.model_name == MODEL
    assert summarizer._target(client._base_url) == (
        "127.0.0.1",
        9999,
        summarizer.GENERATE_PATH,
    )
    assert client._timeout == 7

def test_the_switch_is_the_only_thing_that_decides_whether_the_client_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The task's own case: ``LOCAL_LLM_ENABLED=false`` and nothing is called.

    Written against the stub rather than against the return value, because the
    stub is listening and would answer: a client that dialled first and checked
    the switch afterwards would return the model's prose rather than ``None``,
    so the two are not interchangeable here.
    """
    monkeypatch.setenv(config.LOCAL_LLM_ENABLED_ENV_VAR, "false")

    with _answering(COMPLETION) as (url, received):
        client = _client(url)

        assert client.summarize(PROMPT) is None

    assert received == []


@pytest.mark.parametrize("written", ["false", "FALSE", " no ", "off", "0", "", "   ", "maybe"])
def test_a_switch_that_is_not_written_on_answers_none_and_dials_nobody(
    written: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every spelling that is not an explicit yes, and the default among them.

    Unrecognised is off rather than a refusal: both answers are ordinary
    operating states and only one of them is safe to guess at, so a value this
    reader does not understand leaves the client uncalled.
    """
    monkeypatch.setenv(config.LOCAL_LLM_ENABLED_ENV_VAR, written)

    with _answering(COMPLETION) as (url, received):
        assert _client(url).summarize(PROMPT) is None

    assert received == []


def test_an_unset_switch_leaves_the_client_uncalled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deployment that never read ``.env.example`` is still a safe one."""
    monkeypatch.delenv(config.LOCAL_LLM_ENABLED_ENV_VAR, raising=False)

    with _answering(COMPLETION) as (url, received):
        assert _client(url).summarize(PROMPT) is None

    assert received == []


@pytest.mark.parametrize("written", ["true", "True", "TRUE", " true ", "on", "ON", "1", " yes "])
def test_a_switch_written_on_reaches_the_model(written: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The other direction, so the gate above is a gate and not a dead client.

    Case and surrounding space are folded before the answer is given, because a
    value typed into a shell comes with whatever padding the operator's editor
    put there.
    """
    monkeypatch.setenv(config.LOCAL_LLM_ENABLED_ENV_VAR, written)

    with _answering(COMPLETION) as (url, received):
        assert _client(url).summarize(PROMPT) == ANSWER

    assert len(received) == 1


def test_the_switch_is_read_when_the_client_is_built_not_when_it_is_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The client is off for its whole life once it is built off.

    A long-lived client that re-read the switch per call would follow an
    operator turning it off mid-process, which is the opposite of what a
    ``None`` means here: the caller falls back to the template on every
    document and would keep doing so on half of them.
    """
    monkeypatch.setenv(config.LOCAL_LLM_ENABLED_ENV_VAR, "false")
    off = _client("http://127.0.0.1:1")

    monkeypatch.setenv(config.LOCAL_LLM_ENABLED_ENV_VAR, "true")
    with _answering(COMPLETION) as (_url, received):
        assert off.summarize(PROMPT) is None

    assert received == []


def test_the_switch_is_off_whenever_the_configuration_is_unreadable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A base URL nothing can answer to is not the one thing that turns it on."""
    monkeypatch.setenv(config.LOCAL_LLM_ENABLED_ENV_VAR, "false")

    client = summarizer.LocalLLMClient(base_url="", model=MODEL, timeout=TIMEOUT)

    assert client.summarize(PROMPT) is None


def test_no_request_ever_leaves_the_configured_local_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second half of the task: the only address dialled is the one configured.

    ``socket.create_connection`` is the one place the module reaches a network,
    so wrapping it records every host and port the client would touch on any
    path -- including the ones it refuses before dialling.  The default address
    in :mod:`app.config` is a *different* port, so a client that fell back to
    it after a failure would show up here as a second entry.
    """
    dialled: list[tuple] = []
    real_connect = socket.create_connection

    def recording(address, *args, **kwargs):
        dialled.append(tuple(address))
        return real_connect(address, *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", recording)

    with _answering(COMPLETION) as (url, received):
        assert _client(url).summarize(PROMPT) == ANSWER

    # 17.7's own failure case on a second stub: the address it fails at is
    # still the only one dialled, which is what "no fallback" means when the
    # fallback would be a different port rather than a different path.
    with _answering(COMPLETION, status=500) as (other_url, received_failure):
        assert _client(other_url).summarize(PROMPT) is None

    assert dialled == [
        ("127.0.0.1", urlsplit(url).port),
        ("127.0.0.1", urlsplit(other_url).port),
    ]
    assert len(received) == 1
    assert len(received_failure) == 1


def test_a_switch_that_is_off_dialled_no_address_at_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gate is before the connect, not a filter on what came back.

    Recorded at ``socket.create_connection`` rather than on a stub, because a
    stub that never answered would look identical to a gate that checked
    afterwards -- and a connection to the configured local server is a request
    leaving the host even when no request is sent on it.
    """
    dialled: list[tuple] = []
    real_connect = socket.create_connection

    def recording(address, *args, **kwargs):
        dialled.append(tuple(address))
        return real_connect(address, *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", recording)
    monkeypatch.setenv(config.LOCAL_LLM_ENABLED_ENV_VAR, "false")

    with _answering(COMPLETION) as (_url, received):
        assert _client(_url).summarize(PROMPT) is None

    assert dialled == []
    assert received == []


def test_a_switch_that_is_off_never_looks_at_the_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gate is the first statement, ahead of every other refusal.

    ``_prompt`` is what reads the flag data, so counting its calls is how the
    order is pinned rather than assumed: a gate moved below it would answer
    ``None`` just the same, and the flag data would have been read on the way.
    """
    seen: list[object] = []
    monkeypatch.setattr(summarizer, "_prompt", lambda prompt: seen.append(prompt))
    monkeypatch.setenv(config.LOCAL_LLM_ENABLED_ENV_VAR, "false")

    with _answering(COMPLETION) as (url, received):
        assert _client(url).summarize(PROMPT) is None

    assert seen == []
    assert received == []
def test_the_variable_is_named_the_way_env_example_ships_it() -> None:
    """The name is part of the contract: an operator sets this one variable.

    ``.env.example`` ships ``LOCAL_LLM_ENABLED=false`` and calls it a master
    switch, and a rename of the constant would move both sides of this
    together -- leaving a deployment setting a variable nothing reads.  So the
    name is checked against the shipped file rather than against itself.
    """
    shipped = pathlib.Path(__file__).resolve().parents[3] / ".env.example"

    assert config.LOCAL_LLM_ENABLED_ENV_VAR == "LOCAL_LLM_ENABLED"
    assert f"{config.LOCAL_LLM_ENABLED_ENV_VAR}=false" in shipped.read_text(
        encoding="utf-8"
    )
