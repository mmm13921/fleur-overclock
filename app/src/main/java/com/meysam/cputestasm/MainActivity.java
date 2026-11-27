package com.meysam.cputestasm;
import android.Manifest;
import android.app.Activity;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.*;
import android.location.*;
import android.opengl.*;
import android.os.*;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.nio.*;
import java.util.*;
import java.util.concurrent.*;
import javax.microedition.khronos.egl.EGLConfig;
import javax.microedition.khronos.opengles.GL10;

public class MainActivity extends Activity {
 static { System.loadLibrary("cputest"); }
 private native String runBenchmark(int workers,long iterations);
 private final Handler ui=new Handler(Looper.getMainLooper());
 private final ExecutorService tests=Executors.newFixedThreadPool(2);
 private LinearLayout root,metrics; private TextView result,status; private GLSurfaceView gl; private GpuRenderer gpu;
 private Chart chart; private LocationManager locationManager; private boolean stability=false; private long stabilityEnd=0; private int stabilityMinutes=10;
 private final ArrayList<Float> temps=new ArrayList<>(), fpsValues=new ArrayList<>();
 private String gpsText="GPS: not requested"; private String lastCpu="N/A",lastGpu="N/A",lastBattery="N/A",lastPower="N/A",lastThermal="N/A";
 private final Runnable monitor=new Runnable(){@Override public void run(){sampleMetrics();if(stability && SystemClock.elapsedRealtime()<stabilityEnd){runCpuSlice();ui.postDelayed(this,3000);}else if(stability){stability=false;gpu.enabled=false;status.setText("Stability test completed");append("Stability test completed. Review the recorded metrics.");}}};

 @Override public void onCreate(Bundle b){super.onCreate(b);getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);locationManager=(LocationManager)getSystemService(LOCATION_SERVICE);buildUi();sampleMetrics();ui.postDelayed(new Runnable(){public void run(){sampleMetrics();ui.postDelayed(this,2000);}},2000);}
 private void buildUi(){
  ScrollView scroll=new ScrollView(this);root=new LinearLayout(this);root.setOrientation(1);root.setPadding(16,12,16,24);scroll.addView(root);
  TextView title=new TextView(this);title.setText("CPU / GPU TEST");title.setTextSize(25);title.setTypeface(null,1);root.addView(title);
  TextView device=new TextView(this);device.setText("ARM64 • Assembly + NEON • OpenGL ES 2.0");device.setTextSize(13);root.addView(device);
  status=new TextView(this);status.setText("READY  |  MT6781 compatible");status.setPadding(0,12,0,12);root.addView(status);
  addSection("CPU PERFORMANCE");
  LinearLayout a=row();button(a,"CPU SINGLE",()->runCpu(1));button(a,"CPU ALL-CORE",()->runCpu(Math.max(1,Runtime.getRuntime().availableProcessors())));
  addSection("GPU PERFORMANCE");
  LinearLayout b=row();button(b,"GPU LOAD ON",()->{gpu.enabled=true;status.setText("GPU TEST RUNNING");});button(b,"GPU STOP",()->{gpu.enabled=false;status.setText("GPU TEST STOPPED");});
  gl=new GLSurfaceView(this);gl.setEGLContextClientVersion(2);gpu=new GpuRenderer();gl.setRenderer(gpu);gl.setRenderMode(GLSurfaceView.RENDERMODE_CONTINUOUSLY);gl.setPreserveEGLContextOnPause(true);root.addView(gl,new LinearLayout.LayoutParams(-1,230));
  addSection("STABILITY TEST");
  LinearLayout c=row();button(c,"10 MIN",()->startStability(10));button(c,"30 MIN",()->startStability(30));button(c,"60 MIN",()->startStability(60));
  button(root,"STOP ALL TESTS",()->stopTests());
  addSection("LIVE HARDWARE METRICS");
  metrics=new LinearLayout(this);metrics.setOrientation(1);root.addView(metrics);
  chart=new Chart(this);root.addView(chart,new LinearLayout.LayoutParams(-1,230));
  addSection("GPS / GNSS");
  button(root,"GET GPS FIX",()->requestGps());
  TextView gps=new TextView(this);gps.setText(gpsText);gps.setTag("gps");root.addView(gps);
  addSection("BENCHMARK RESULTS / LOG");
  result=new TextView(this);result.setTextSize(12);result.setTypeface(Typeface.MONOSPACE);result.setText("No benchmark run yet.");root.addView(result);
  setContentView(scroll);
 }
 private LinearLayout row(){LinearLayout x=new LinearLayout(this);root.addView(x);return x;}
 private void addSection(String s){TextView t=new TextView(this);t.setText("\n"+s);t.setTextSize(16);t.setTypeface(null,1);root.addView(t);}
 private void button(LinearLayout p,String s,Runnable r){Button b=new Button(this);b.setText(s);b.setTextSize(11);b.setOnClickListener(v->r.run());p.addView(b,new LinearLayout.LayoutParams(0,-2,1));}
 private void append(String s){result.setText(s+"\n\n"+result.getText());}
 private void runCpu(int workers){status.setText("CPU benchmark running ("+workers+" worker(s))");tests.execute(()->{String out=runBenchmark(workers,18000000L);ui.post(()->{status.setText("CPU benchmark finished");append(out);});});}
 private void runCpuSlice(){tests.execute(()->runBenchmark(Math.max(1,Runtime.getRuntime().availableProcessors()),3000000L));}
 private void startStability(int minutes){stability=true;stabilityMinutes=minutes;stabilityEnd=SystemClock.elapsedRealtime()+minutes*60000L;gpu.enabled=true;status.setText("STABILITY TEST RUNNING • "+minutes+" min");append("Started combined CPU + GPU stability run for "+minutes+" minutes.");ui.removeCallbacks(monitor);ui.post(monitor);}
 private void stopTests(){stability=false;gpu.enabled=false;ui.removeCallbacks(monitor);status.setText("Tests stopped");append("Test stopped by user.");}
 private String read(String path){try(BufferedReader r=new BufferedReader(new FileReader(path))){String s=r.readLine();return s==null?"N/A":s.trim();}catch(Exception e){return "N/A";}}
 private float thermalC(){float max=-1;File d=new File("/sys/class/thermal");File[] z=d.listFiles();if(z!=null)for(File f:z)if(f.getName().startsWith("thermal_zone")){String s=read(f.getPath()+"/temp");try{float v=Float.parseFloat(s);if(v>1000)v/=1000f;if(v>max&&v<150)max=v;}catch(Exception ignored){}}return max;}
 private void sampleMetrics(){
  lastCpu="little "+read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")+" kHz | big "+read("/sys/devices/system/cpu/cpu7/cpufreq/scaling_cur_freq")+" kHz";
  String[] gp={"/sys/class/devfreq/13000000.mali/cur_freq","/sys/devices/platform/13000000.mali/devfreq/13000000.mali/cur_freq","/sys/kernel/ged/hal/gpu_clock"};
  lastGpu="N/A";for(String p:gp){String v=read(p);if(!"N/A".equals(v)){lastGpu=v;break;}}
  Intent bat=registerReceiver(null,new IntentFilter(Intent.ACTION_BATTERY_CHANGED));int mv=bat==null?-1:bat.getIntExtra(BatteryManager.EXTRA_VOLTAGE,-1);int pct=bat==null?-1:bat.getIntExtra(BatteryManager.EXTRA_LEVEL,-1);int bt=bat==null?-1:bat.getIntExtra(BatteryManager.EXTRA_TEMPERATURE,-1);int ua=0;try{ua=((BatteryManager)getSystemService(BATTERY_SERVICE)).getIntProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW);}catch(Exception ignored){}
  lastBattery=pct+"% | "+mv+" mV | battery temp "+(bt<0?"N/A":String.format(Locale.US,"%.1f°C",bt/10f));
  lastPower=mv>0?String.format(Locale.US,"%.2f W (battery-side estimate)",Math.abs(ua/1000000.0)*(mv/1000.0)):"N/A";
  float t=thermalC();lastThermal=t<0?"N/A (thermal sysfs restricted)":String.format(Locale.US,"%.1f°C max thermal-zone",t);
  if(t>=0){temps.add(t);if(temps.size()>90)temps.remove(0);}fpsValues.add(gpu.fps);if(fpsValues.size()>90)fpsValues.remove(0);
  metrics.removeAllViews();String[] lines={"CPU frequency: "+lastCpu,"GPU frequency: "+lastGpu,"Thermal: "+lastThermal,"Battery: "+lastBattery,"Power: "+lastPower,"GPU FPS: "+String.format(Locale.US,"%.1f",gpu.fps)+" | frames "+gpu.frames,"Stability: "+(stability?"RUNNING":"idle")};
  for(String s:lines){TextView v=new TextView(this);v.setText(s);v.setTextSize(13);metrics.addView(v);}chart.setData(temps,fpsValues);
  View v=root.findViewWithTag("gps");if(v instanceof TextView)((TextView)v).setText(gpsText);
 }
 private void requestGps(){
  if(checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)!=PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION,Manifest.permission.ACCESS_COARSE_LOCATION},21);return;}
  try{boolean on=locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER);Location old=locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER);gpsText="GPS enabled: "+on+(old==null?" | waiting for fix":" | last fix accuracy "+old.getAccuracy()+" m, age "+((System.currentTimeMillis()-old.getTime())/1000)+" s");if(on)locationManager.requestLocationUpdates(LocationManager.GPS_PROVIDER,1000,0,gpsListener);sampleMetrics();}catch(Exception e){gpsText="GPS error: "+e.getMessage();sampleMetrics();}
 }
 private final LocationListener gpsListener=new LocationListener(){@Override public void onLocationChanged(Location l){gpsText=String.format(Locale.US,"GNSS FIX • %.5f, %.5f • accuracy %.1f m • %d satellites not exposed by Android location API",l.getLatitude(),l.getLongitude(),l.getAccuracy());try{locationManager.removeUpdates(this);}catch(Exception ignored){}sampleMetrics();}};
 @Override public void onRequestPermissionsResult(int r,String[] p,int[] g){super.onRequestPermissionsResult(r,p,g);if(r==21&&g.length>0&&g[0]==PackageManager.PERMISSION_GRANTED)requestGps();}
 @Override protected void onPause(){super.onPause();if(gl!=null)gl.onPause();}
 @Override protected void onResume(){super.onResume();if(gl!=null)gl.onResume();}
 @Override protected void onDestroy(){stopTests();tests.shutdownNow();try{locationManager.removeUpdates(gpsListener);}catch(Exception ignored){}super.onDestroy();}

 private static class GpuRenderer implements GLSurfaceView.Renderer{
  volatile boolean enabled=false;volatile float fps=0;volatile long frames=0;int program,pos,timeLoc;long windowStart=System.nanoTime(),windowFrames=0;
  private final FloatBuffer vertices=ByteBuffer.allocateDirect(8*4).order(ByteOrder.nativeOrder()).asFloatBuffer();
  public void onSurfaceCreated(GL10 gl,EGLConfig config){
   String vs="attribute vec2 aPos; varying vec2 uv; void main(){uv=aPos*0.5+0.5;gl_Position=vec4(aPos,0.0,1.0);}";
   String fs="precision highp float; varying vec2 uv; uniform float uTime; void main(){vec2 p=(uv-0.5)*2.0;float z=0.0;for(int i=0;i<96;i++){p=abs(p)/max(dot(p,p),0.015)-0.71;z+=sin(p.x*9.7+uTime)*cos(p.y*11.3-uTime*0.7);}gl_FragColor=vec4(0.5+0.5*sin(z),0.5+0.5*cos(z*0.7),0.5+0.5*sin(z*0.31),1.0);}";
   int v=compile(35633,vs),f=compile(35632,fs);program=GLES20.glCreateProgram();GLES20.glAttachShader(program,v);GLES20.glAttachShader(program,f);GLES20.glLinkProgram(program);pos=GLES20.glGetAttribLocation(program,"aPos");timeLoc=GLES20.glGetUniformLocation(program,"uTime");
   vertices.put(new float[]{-1,-1,1,-1,-1,1,1,1}).position(0);
  }
  int compile(int type,String src){int s=GLES20.glCreateShader(type);GLES20.glShaderSource(s,src);GLES20.glCompileShader(s);return s;}
  public void onSurfaceChanged(GL10 gl,int w,int h){GLES20.glViewport(0,0,w,h);}
  public void onDrawFrame(GL10 gl){if(!enabled){GLES20.glClearColor(0.04f,0.05f,0.08f,1);GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT);return;}
   GLES20.glUseProgram(program);GLES20.glUniform1f(timeLoc,(System.nanoTime()-windowStart)/1.0e9f);GLES20.glEnableVertexAttribArray(pos);GLES20.glVertexAttribPointer(pos,2,GLES20.GL_FLOAT,false,0,vertices);GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP,0,4);frames++;windowFrames++;long now=System.nanoTime();if(now-windowStart>=1000000000L){fps=windowFrames*1.0e9f/(now-windowStart);windowFrames=0;windowStart=now;}
  }
 }
 private static class Chart extends View{
  Paint p=new Paint(3);ArrayList<Float> t=new ArrayList<>(),f=new ArrayList<>();
  Chart(Activity a){super(a);setLayerType(View.LAYER_TYPE_SOFTWARE,null);}
  void setData(ArrayList<Float> a,ArrayList<Float>b){t=new ArrayList<>(a);f=new ArrayList<>(b);postInvalidate();}
  protected void onDraw(Canvas c){super.onDraw(c);float w=getWidth(),h=getHeight();p.setColor(Color.DKGRAY);p.setTextSize(27);c.drawText("THERMAL °C / GPU FPS",12,28,p);p.setTextSize(18);p.setColor(Color.GRAY);for(int i=0;i<4;i++){float y=45+i*(h-60)/3;c.drawLine(8,y,w-8,y,p);}drawLine(c,t,w,h,Color.RED,0,100);drawLine(c,f,w,h,Color.BLUE,0,120);p.setColor(Color.RED);c.drawText("Temp",12,h-8,p);p.setColor(Color.BLUE);c.drawText("FPS",100,h-8,p);}
  void drawLine(Canvas c,ArrayList<Float>d,float w,float h,int color,float min,float max){if(d.size()<2)return;p.setColor(color);p.setStrokeWidth(3);Path path=new Path();for(int i=0;i<d.size();i++){float x=8+i*(w-16)/(Math.max(1,d.size()-1));float val=Math.max(min,Math.min(max,d.get(i)));float y=42+(h-62)*(1-(val-min)/(max-min));if(i==0)path.moveTo(x,y);else path.lineTo(x,y);}c.drawPath(path,p);}
 }
}