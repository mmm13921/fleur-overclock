package com.meysam.cputestasm;

import android.app.Activity;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    static { System.loadLibrary("cputest"); }
    private native String runBenchmark(int workers, long iterations);
    private TextView output;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout root = new LinearLayout(this); root.setOrientation(1); root.setPadding(24,24,24,24);
        TextView title = new TextView(this); title.setText("ARM64 Assembly + NEON CPU Test\n\nMTK / ARM64 benchmark"); title.setTextSize(22); root.addView(title);
        Button single = new Button(this); single.setText("Single-core test"); root.addView(single);
        Button multi = new Button(this); multi.setText("All-core test (available CPUs)"); root.addView(multi);
        output = new TextView(this); output.setTextSize(15); output.setText("Ready. Run tests while the phone is cool and unplugged."); root.addView(output);
        ScrollView scroll = new ScrollView(this); scroll.addView(root); setContentView(scroll);
        single.setOnClickListener(v -> run(1));
        multi.setOnClickListener(v -> run(Math.max(1, Runtime.getRuntime().availableProcessors())));
    }
    private void run(int workers) {
        output.setText("Running " + workers + " worker(s)...\nKeep the screen on; stop if the device gets too hot.");
        executor.execute(() -> { String result = runBenchmark(workers, 12000000L); runOnUiThread(() -> output.setText(result)); });
    }
    @Override protected void onDestroy() { executor.shutdownNow(); super.onDestroy(); }
}
