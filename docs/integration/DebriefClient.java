import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * Minimal client for il2_debrief.exe (IL-2 Campaign Tracker).
 *
 * Runs the analyser on one mission's log and returns the path of the JSON it wrote.
 * No dependencies; Java 11+. Parse the returned file with Gson, Jackson, etc.
 * Interface contract: DEBRIEF_CLI.md.
 */
public final class DebriefClient {

    /** The highest schema_version this client understands. */
    public static final int SUPPORTED_SCHEMA_VERSION = 1;

    private final Path exePath;
    private final long timeoutSeconds;

    public DebriefClient(Path exePath, long timeoutSeconds) {
        this.exePath = exePath;
        this.timeoutSeconds = timeoutSeconds;
    }

    /**
     * @param logs    one .mlg file, or the .txt part(s) of one mission ([0].txt, [1].txt, ...)
     * @param outJson where the analyser should write its JSON
     * @return outJson, once the analyser has written it
     * @throws DebriefException if the analyser reports an error, times out or cannot be started
     */
    public Path analyse(List<Path> logs, Path outJson) throws DebriefException {
        List<String> cmd = new ArrayList<>();
        cmd.add(exePath.toString());
        for (Path log : logs) {
            cmd.add(log.toString());
        }
        cmd.add("--out");
        cmd.add(outJson.toString());

        ProcessBuilder pb = new ProcessBuilder(cmd)
                // stderr is diagnostics only; discard it so the pipe can never fill and block.
                .redirectError(ProcessBuilder.Redirect.DISCARD);

        Process process;
        try {
            process = pb.start();
        } catch (IOException e) {
            throw new DebriefException(-1, "start_failed", "Cannot start " + exePath + ": " + e.getMessage());
        }

        try {
            String statusLine;
            try (InputStream stdout = process.getInputStream()) {
                statusLine = new String(stdout.readAllBytes(), StandardCharsets.UTF_8).trim();
            }
            if (!process.waitFor(timeoutSeconds, TimeUnit.SECONDS)) {
                process.destroyForcibly();
                throw new DebriefException(-1, "timeout", "il2_debrief did not finish in " + timeoutSeconds + " s");
            }
            int exit = process.exitValue();
            if (exit != 0) {
                // statusLine is {"ok": false, "error_code": "...", "error": "..."}
                throw new DebriefException(exit, extract(statusLine, "error_code"), extract(statusLine, "error"));
            }
            if (!Files.isRegularFile(outJson)) {
                throw new DebriefException(exit, "no_output", "il2_debrief reported success but wrote no file");
            }
            return outJson;
        } catch (IOException e) {
            throw new DebriefException(-1, "io_error", e.getMessage());
        } catch (InterruptedException e) {
            process.destroyForcibly();
            Thread.currentThread().interrupt();
            throw new DebriefException(-1, "interrupted", "Interrupted while waiting for il2_debrief");
        }
    }

    /** Pull one string field out of the one-line status JSON (use your JSON library in real code). */
    private static String extract(String json, String key) {
        String marker = "\"" + key + "\": \"";
        int start = json.indexOf(marker);
        if (start < 0) {
            return json;
        }
        start += marker.length();
        int end = json.indexOf('"', start);
        return end < 0 ? json.substring(start) : json.substring(start, end);
    }

    public static final class DebriefException extends Exception {
        private static final long serialVersionUID = 1L;

        public final int exitCode;
        public final String errorCode;

        DebriefException(int exitCode, String errorCode, String message) {
            super(message);
            this.exitCode = exitCode;
            this.errorCode = errorCode;
        }
    }

    /** Example: java DebriefClient.java <il2_debrief.exe> <out.json> <log> [<log> ...] */
    public static void main(String[] args) throws Exception {
        DebriefClient client = new DebriefClient(Paths.get(args[0]), 60);
        List<Path> logs = new ArrayList<>();
        for (int i = 2; i < args.length; i++) {
            logs.add(Paths.get(args[i]));
        }
        try {
            Path json = client.analyse(logs, Paths.get(args[1]));
            System.out.println("Wrote " + json);
        } catch (DebriefException e) {
            System.out.println("Failed (exit " + e.exitCode + ", " + e.errorCode + "): " + e.getMessage());
        }
    }
}
