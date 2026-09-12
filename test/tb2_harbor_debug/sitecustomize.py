import sys
import time

try:
    from harbor.environments.docker.docker import DockerEnvironment

    _orig = DockerEnvironment._run_docker_compose_command

    async def _debug_run(
        self,
        command,
        check=True,
        timeout_sec=None,
        stdin_data=None,
        on_output=None,
    ):
        is_exec = bool(command) and command[0] == "exec"
        t0 = time.monotonic()

        if is_exec:
            print(
                f"\n[TB2DBG] compose exec START "
                f"timeout_sec={timeout_sec!r}\n"
                f"[TB2DBG] command={command!r}",
                file=sys.stderr,
                flush=True,
            )

        try:
            result = await _orig(
                self,
                command,
                check=check,
                timeout_sec=timeout_sec,
                stdin_data=stdin_data,
                on_output=on_output,
            )

            if is_exec:
                dt = time.monotonic() - t0
                print(
                    f"\n[TB2DBG] compose exec END "
                    f"elapsed={dt:.3f}s "
                    f"return_code={result.return_code!r}",
                    file=sys.stderr,
                    flush=True,
                )

            return result

        except BaseException as e:
            if is_exec:
                dt = time.monotonic() - t0
                print(
                    f"\n[TB2DBG] compose exec EXCEPTION "
                    f"elapsed={dt:.3f}s "
                    f"type={type(e).__name__} "
                    f"value={e!r}",
                    file=sys.stderr,
                    flush=True,
                )
            raise

    DockerEnvironment._run_docker_compose_command = _debug_run

except Exception as e:
    print(
        f"[TB2DBG] sitecustomize install failed: {e!r}",
        file=sys.stderr,
        flush=True,
    )
