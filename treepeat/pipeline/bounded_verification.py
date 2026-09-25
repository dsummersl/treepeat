import multiprocessing
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess

from treepeat.models.shingle import ShingledRegion
from treepeat.models.similarity import SimilarRegionGroup
from treepeat.pipeline.rules.models import Rule


def _verification_worker(connection: Connection, rules: list[Rule]) -> None:
    """Isolate matching so a deadline can be enforced on every platform."""
    from treepeat.pipeline.verification import _build_region_lookup, _verify_group_pairwise_similarity

    connection.send("ready")
    try:
        while True:
            group, shingles = connection.recv()
            try:
                score = _verify_group_pairwise_similarity(group.regions, _build_region_lookup(shingles), rules)
                connection.send((score, None))
            except Exception as error:
                connection.send((None, str(error)))
    except EOFError:
        pass
    finally:
        connection.close()


class BoundedVerifier:
    """Reuse one worker, replacing it when a candidate times out or fails."""

    def __init__(self, timeout: float, rules: list[Rule]):
        self.timeout = timeout
        self.rules = rules
        self.process: BaseProcess | None = None
        self.connection: Connection | None = None

    def _start(self) -> None:
        context = multiprocessing.get_context("spawn")
        self.connection, child = context.Pipe()
        self.process = context.Process(target=_verification_worker, args=(child, self.rules), daemon=True)
        self.process.start()
        child.close()
        # Interpreter startup is separate from the candidate's verification budget.
        if not self.connection.poll(30) or self.connection.recv() != "ready":
            self.close()
            raise RuntimeError("Verification worker failed to start")

    def verify(self, group: SimilarRegionGroup, shingles: list[ShingledRegion]) -> float:
        if self.process is None:
            self._start()
        assert self.connection is not None
        try:
            self.connection.send((group, shingles))
            return self._receive_score(self.connection)
        except (TimeoutError, EOFError, OSError, RuntimeError):
            self.close()
            raise

    def _receive_score(self, connection: Connection) -> float:
        if not connection.poll(self.timeout):
            raise TimeoutError(f"Candidate group exceeded {self.timeout:g}s verification budget")
        score, error = connection.recv()
        if error is not None:
            raise RuntimeError(error)
        return float(score)

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
        if self.process is not None:
            self.process.terminate()
            self.process.join(timeout=1)
            if self.process.is_alive():
                self.process.kill()
                self.process.join()
            self.process.close()
        self.process = None
        self.connection = None
