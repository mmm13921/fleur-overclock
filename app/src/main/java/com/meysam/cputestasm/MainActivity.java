package com.meysam.cputestasm;
import android.Manifest;
import android.app.Activity;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.*;
import android.graphics.drawable.GradientDrawable;
import android.location.*;
import android.opengl.*;
import android.net.*;
import android.os.*;
import android.hardware.*;
import android.view.*;
import android.view.Display;
import android.widget.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.Locale;

public class MainActivity extends Activity {
 static { System.loadLibrary("cputest"); }
 private native String runBenchmark(int workers,long iterations);
 private final Handler ui=new Handler(Looper.getMainLooper());
 private final ExecutorService worker=Executors.newSingleThreadExecutor();
 private LinearLayout root,sections,cpuBox,sensorBox;
 private TextView status,gpsStatus,benchmark;
 private final Map<Integer,long[]> cpuPrev=new HashMap<>();
 private final Map<Integer,Float> cpuUse=new HashMap<>();
 private final Map<Integer,String> sensorValues=new HashMap<>();
 private final Map<Integer,TextView> sensorViews=new HashMap<>();
 private SensorManager sensorManager;
 private LocationManager locationManager;
 private GnssStatus.Callback gnssCallback;
 private LocationListener locationListener;
 private boolean gpsActive=false;
 private int satellites=0,usedSatellites=0;
 private float avgCn0=0;
 private GLSurfaceView gl;
 private LoadRenderer renderer;
 private boolean gpuStress=false;
 private final Runnable sampler=new Runnable(){public void run(){sampleAll();ui.postDelayed(this,1500);}};
 @Override public void onCreate(Bundle b){super.onCreate(b);getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);sensorManager=(SensorManager)getSystemService(SENSOR_SERVICE);locationManager=(LocationManager)getSystemService(LOCATION_SERVICE);buildUi();registerSensors();sampleAll();ui.postDelayed(sampler,1500);}
 private int dp(float v){return (int)(v*getResources().getDisplayMetrics().density+0.5f);}
 private GradientDrawable bg(int color){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(14));d.setStroke(dp(1),0xff29384a);return d;}
 private TextView text(String s,int size,int color,boolean bold){TextView t=new TextView(this);t.setText(s);t.setTextSize(size);t.setTextColor(color);if(bold)t.setTypeface(null,1);return t;}
 private void buildUi(){
  ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);root=new LinearLayout(this);root.setOrientation(1);root.setPadding(dp(14),dp(16),dp(14),dp(28));root.setBackgroundColor(0xff080e17);scroll.addView(root);
  root.addView(text("SILICON / SoC MONITOR",23,0xffe7f1ff,true));
  root.addView(text("MT6781 • CPU / GPU / MEMORY / POWER / RADIO / GNSS",11,0xff8ea6c2,false));
  status=text("INITIALIZING HARDWARE TELEMETRY",12,0xff63d7a2,true);status.setPadding(0,dp(12),0,dp(12));root.addView(status);
  section("SILICON ACTIVITY ESTIMATE","Software-derived activity index. Not a physical transistor-state measurement.");
  addCard("TRANSISTOR SWITCHING ESTIMATE","switching");addCard("CPU CLUSTERS & PER-CORE TELEMETRY","cpu");addCard("GPU / GRAPHICS ENGINE","gpu");addCard("MEMORY / MEMORY CONTROLLER","memory");addCard("STORAGE I/O","storage");addCard("INTERCONNECT / DEVFREQ DOMAINS","devfreq");addCard("MODEM / NETWORK INTERFACES","network");addCard("POWER / BATTERY","power");addCard("THERMAL ZONES","thermal");addCard("SENSORS","sensors");addCard("DISPLAY ENGINE","display");addCard("GNSS / GPS MONITOR","gnss");
  section("LOAD TEST","Optional workload for observing how telemetry changes under load.");
  LinearLayout tests=cardContainer();Button cpu=button("RUN CPU TEST");cpu.setOnClickListener(v->runCpuTest());tests.addView(cpu);Button gpu=button("GPU LOAD ON / OFF");gpu.setOnClickListener(v->{gpuStress=!gpuStress;renderer.enabled=gpuStress;status.setText(gpuStress?"GPU LOAD ACTIVE":"GPU LOAD STOPPED");});tests.addView(gpu);Button stop=button("STOP GPU LOAD");stop.setOnClickListener(v->{gpuStress=false;renderer.enabled=false;status.setText("GPU LOAD STOPPED");});tests.addView(stop);
  gl=new GLSurfaceView(this);gl.setEGLContextClientVersion(2);renderer=new LoadRenderer();gl.setRenderer(renderer);gl.setRenderMode(GLSurfaceView.RENDERMODE_CONTINUOUSLY);gl.setLayoutParams(new LinearLayout.LayoutParams(-1,dp(110)));tests.addView(gl);
  benchmark=text("No CPU test executed.",11,0xffb7c8dc,false);tests.addView(benchmark);root.addView(tests);
  TextView note=text("Telemetry availability depends on kernel drivers and Android permissions. Unavailable sysfs nodes are shown as N/A; estimates are labeled.",10,0xff71859d,false);note.setPadding(dp(4),dp(12),dp(4),0);root.addView(note);
  setContentView(scroll);
 }
 private void section(String title,String subtitle){TextView t=text(title,14,0xff72c7ff,true);t.setPadding(dp(3),dp(18),0,dp(4));root.addView(t);if(subtitle!=null)root.addView(text(subtitle,10,0xff7f94ad,false));}
 private LinearLayout cardContainer(){LinearLayout c=new LinearLayout(this);c.setOrientation(1);c.setPadding(dp(12),dp(10),dp(12),dp(10));c.setBackground(bg(0xff111c2a));LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.setMargins(0,dp(6),0,dp(6));c.setLayoutParams(lp);return c;}
 private void addCard(String title,String key){LinearLayout c=cardContainer();c.addView(text(title,12,0xffc7d9ed,true));TextView v=text("Reading hardware telemetry…",12,0xff9eb2c9,false);v.setTag(key);v.setPadding(0,dp(7),0,0);c.addView(v);if("cpu".equals(key)){cpuBox=new LinearLayout(this);cpuBox.setOrientation(1);c.addView(cpuBox);}if("sensors".equals(key)){sensorBox=new LinearLayout(this);sensorBox.setOrientation(1);c.addView(sensorBox);}if("gnss".equals(key)){Button b=button("START GNSS MONITOR");b.setOnClickListener(x->startGnss());c.addView(b);gpsStatus=v;}root.addView(c);}
 private Button button(String s){Button b=new Button(this);b.setText(s);b.setTextSize(10);b.setTextColor(0xffe9f4ff);b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(0xff24517a));return b;}
 private TextView value(String key){return (TextView)root.findViewWithTag(key);}
 private String read(String p){try(BufferedReader r=new BufferedReader(new FileReader(p))){String s=r.readLine();return s==null?"N/A":s.trim();}catch(Exception e){return "N/A";}}
 private long number(String s){try{return Long.parseLong(s.trim());}catch(Exception e){return -1;}}
 private String freq(String path){String s=read(path);long n=number(s);if(n<0)return "N/A";return n>=100000?String.format(Locale.US,"%.0f MHz",n/1000.0):n+" kHz";}
 private String cpuFrequencies(){StringBuilder b=new StringBuilder();for(int i=0;i<Runtime.getRuntime().availableProcessors();i++){String base="/sys/devices/system/cpu/cpu"+i+"/cpufreq/";String online=read("/sys/devices/system/cpu/cpu"+i+"/online");if(i==0&&"N/A".equals(online))online="1";String f=freq(base+"scaling_cur_freq");String gov=read(base+"scaling_governor");b.append("CPU").append(i).append(" [").append("0".equals(online)?"OFF":"ON").append("] ").append(f).append(" · ").append(gov).append("\n");}return b.toString().trim();}
 private void sampleCpu(){
  cpuBox.removeAllViews();StringBuilder all=new StringBuilder();long[][] now=readCpuStat();
  for(int i=0;i<Runtime.getRuntime().availableProcessors();i++){long[] cur=i<now.length?now[i]:null;float use=0;if(cur!=null){long[] prev=cpuPrev.get(i);if(prev!=null){long dt=cur[0]-prev[0],di=cur[1]-prev[1];if(dt>0)use=Math.max(0,Math.min(100,(dt-di)*100f/dt));}cpuPrev.put(i,cur);cpuUse.put(i,use);}
   String online=read("/sys/devices/system/cpu/cpu"+i+"/online");if(i==0&&"N/A".equals(online))online="1";String f=freq("/sys/devices/system/cpu/cpu"+i+"/cpufreq/scaling_cur_freq");String gov=read("/sys/devices/system/cpu/cpu"+i+"/cpufreq/scaling_governor");
   LinearLayout line=new LinearLayout(this);line.setOrientation(1);TextView label=text("CPU"+i+"  "+("0".equals(online)?"OFFLINE":"ONLINE")+"  "+f+"  "+String.format(Locale.US,"%.0f%%",use),10,0xffb9cce0,false);line.addView(label);ProgressBar bar=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);bar.setMax(100);bar.setProgress((int)use);line.addView(bar);cpuBox.addView(line);all.append("CPU").append(i).append(": ").append(f).append(", ").append(gov).append(", ").append(String.format(Locale.US,"%.0f%%",use)).append("\n");
  }
  TextView v=value("cpu");if(v!=null)v.setText(all.toString().trim());
 }
 private long[][] readCpuStat(){ArrayList<long[]> out=new ArrayList<>();try(BufferedReader r=new BufferedReader(new FileReader("/proc/stat"))){String s;while((s=r.readLine())!=null&&s.startsWith("cpu")){String[] a=s.trim().split("\\s+");if(a[0].equals("cpu"))continue;long total=0,idle=0;for(int j=1;j<a.length;j++){long x=Long.parseLong(a[j]);total+=x;if(j==4||j==5)idle+=x;}out.add(new long[]{total,idle});}}catch(Exception ignored){}return out.toArray(new long[0][]);}
 private String gpuInfo(){
  String[] freqPaths={"/sys/class/devfreq/13000000.mali/cur_freq","/sys/devices/platform/13000000.mali/devfreq/13000000.mali/cur_freq","/sys/kernel/ged/hal/gpu_clock"};
  String[] loadPaths={"/sys/class/devfreq/13000000.mali/load","/sys/class/devfreq/13000000.mali/utilization","/sys/kernel/ged/hal/gpu_utilization","/sys/kernel/ged/hal/gpu_busy"};
  String f="N/A",l="N/A";for(String p:freqPaths){String s=read(p);if(!"N/A".equals(s)){long n=number(s);f=n>100000?String.format(Locale.US,"%.0f MHz",n/1000.0):s;break;}}for(String p:loadPaths){String s=read(p);if(!"N/A".equals(s)){l=s;break;}}
  return "Frequency: "+f+"\nUtilization / busy: "+l+"\nDriver: "+read("/sys/kernel/ged/hal/version")+"\nGPU stress: "+(gpuStress?"ACTIVE":"OFF")+"\nNote: utilization is driver-dependent; N/A means no readable node.";
 }
 private String memoryInfo(){Map<String,Long> m=new HashMap<>();try(BufferedReader r=new BufferedReader(new FileReader("/proc/meminfo"))){String s;while((s=r.readLine())!=null){String[] a=s.split(":");if(a.length>1){String[] n=a[1].trim().split("\\s+");m.put(a[0],Long.parseLong(n[0]));}}}catch(Exception ignored){}long total=m.getOrDefault("MemTotal",0L),avail=m.getOrDefault("MemAvailable",0L),used=total-avail;String z=read("/sys/block/zram0/mm_stat");return String.format(Locale.US,"RAM: %.0f / %.0f MB used (%.1f%%)\nAvailable: %.0f MB\nSwap total: %.0f MB · swap free: %.0f MB\nZRAM mm_stat: %s\nMemory bandwidth: not exposed by generic Android sysfs",used/1024.0,total/1024.0,total>0?used*100.0/total:0,avail/1024.0,m.getOrDefault("SwapTotal",0L)/1024.0,m.getOrDefault("SwapFree",0L)/1024.0,z);}
 private String storageInfo(){String s=read("/sys/block/mmcblk0/stat");if("N/A".equals(s))s=read("/sys/block/sda/stat");if("N/A".equals(s))return "Block I/O counters: unavailable";try{String[] a=s.split("\\s+");long sectorsRead=Long.parseLong(a[2]),sectorsWritten=Long.parseLong(a[6]);return String.format(Locale.US,"Read since boot: %.2f GB\nWritten since boot: %.2f GB\nDevice stats: %s",sectorsRead*512/1e9,sectorsWritten*512/1e9,s);}catch(Exception e){return s;}}
 private String devfreqInfo(){StringBuilder b=new StringBuilder();File d=new File("/sys/class/devfreq");File[] fs=d.listFiles();if(fs!=null)for(File f:fs){String cur=read(f.getPath()+"/cur_freq"),max=read(f.getPath()+"/max_freq"),gov=read(f.getPath()+"/governor");if(!"N/A".equals(cur)||!"N/A".equals(max))b.append(f.getName()).append("\n current: ").append(cur).append(" · max: ").append(max).append(" · governor: ").append(gov).append("\n");}return b.length()==0?"No readable devfreq domains.":b.toString().trim();}
 private String networkInfo(){StringBuilder b=new StringBuilder();try(BufferedReader r=new BufferedReader(new FileReader("/proc/net/dev"))){String s;while((s=r.readLine())!=null){if(!s.contains(":"))continue;String[] a=s.trim().replace(":"," ").split("\\s+");if(a.length<10)continue;try{long rx=Long.parseLong(a[1]),tx=Long.parseLong(a[9]);b.append(a[0]).append("  RX ").append(bytes(rx)).append(" · TX ").append(bytes(tx)).append("\n");}catch(Exception ignored){}}}catch(Exception ignored){}ConnectivityManager cm=(ConnectivityManager)getSystemService(CONNECTIVITY_SERVICE);Network n=cm==null?null:cm.getActiveNetwork();NetworkCapabilities c=n==null?null:cm.getNetworkCapabilities(n);String transport="none";if(c!=null){if(c.hasTransport(NetworkCapabilities.TRANSPORT_WIFI))transport="Wi-Fi";else if(c.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR))transport="Cellular";else if(c.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET))transport="Ethernet";}return "Active transport: "+transport+"\n"+b.toString().trim()+"\nRadio signal details require vendor/telephony access; interface counters are shown instead.";}
 private String bytes(long n){if(n>1e9)return String.format(Locale.US,"%.2f GB",n/1e9);if(n>1e6)return String.format(Locale.US,"%.1f MB",n/1e6);return n+" B";}
 private String powerInfo(){Intent b=registerReceiver(null,new IntentFilter(Intent.ACTION_BATTERY_CHANGED));if(b==null)return "Battery service unavailable";int level=b.getIntExtra(BatteryManager.EXTRA_LEVEL,-1),scale=b.getIntExtra(BatteryManager.EXTRA_SCALE,100),mv=b.getIntExtra(BatteryManager.EXTRA_VOLTAGE,-1),temp=b.getIntExtra(BatteryManager.EXTRA_TEMPERATURE,-1),status=b.getIntExtra(BatteryManager.EXTRA_STATUS,-1),plug=b.getIntExtra(BatteryManager.EXTRA_PLUGGED,0);BatteryManager bm=(BatteryManager)getSystemService(BATTERY_SERVICE);int ua=bm==null?0:bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW);String state=status==BatteryManager.BATTERY_STATUS_CHARGING?"Charging":status==BatteryManager.BATTERY_STATUS_FULL?"Full":status==BatteryManager.BATTERY_STATUS_DISCHARGING?"Discharging":"Unknown";double watts=mv>0?Math.abs(ua/1000000.0)*(mv/1000.0):0;return String.format(Locale.US,"Level: %d%% · %s · plugged=%d\nVoltage: %d mV · current: %d µA\nBattery temperature: %s\nBattery-side power estimate: %.3f W\nPower rails / PMIC per-rail telemetry: not exposed by standard Android API",scale>0?level*100/scale:level,state,plug,mv,ua,temp>=0?String.format(Locale.US,"%.1f°C",temp/10f):"N/A",watts);}
 private String thermalInfo(){File d=new File("/sys/class/thermal");File[] fs=d.listFiles();if(fs==null)return "Thermal sysfs unavailable";StringBuilder b=new StringBuilder();for(File f:fs){if(!f.getName().startsWith("thermal_zone"))continue;String t=read(f.getPath()+"/temp"),type=read(f.getPath()+"/type");long n=number(t);if(n>=0){double c=n>1000?n/1000.0:n/10.0;b.append(type).append(" · ").append(String.format(Locale.US,"%.1f°C",c)).append("\n");}}return b.length()==0?"No readable thermal zones.":b.toString().trim();}
 private String displayInfo(){Display d=getWindowManager().getDefaultDisplay();android.util.DisplayMetrics m=new android.util.DisplayMetrics();d.getRealMetrics(m);float hz=0;try{hz=d.getMode().getRefreshRate();}catch(Exception ignored){}return String.format(Locale.US,"Resolution: %d × %d\nDensity: %.1f dpi\nRefresh rate: %.2f Hz\nDisplay ID: %d\nBrightness: %s",m.widthPixels,m.heightPixels,m.densityDpi,hz,d.getDisplayId(),read("/sys/class/backlight/panel0-backlight/brightness"));}
 private void registerSensors(){List<Sensor> list=sensorManager.getSensorList(Sensor.TYPE_ALL);for(Sensor s:list){TextView v=text(s.getName()+" · "+s.getVendor()+"\nWaiting for sensor sample…",10,0xffa9bfd5,false);v.setPadding(0,dp(4),0,dp(4));sensorBox.addView(v);sensorViews.put(s.getType(),v);sensorManager.registerListener(sensorListener,s,SensorManager.SENSOR_DELAY_NORMAL);}}
 private final SensorEventListener sensorListener=new SensorEventListener(){public void onSensorChanged(SensorEvent e){StringBuilder b=new StringBuilder();for(int i=0;i<e.values.length;i++){if(i>0)b.append(", ");b.append(String.format(Locale.US,"%.3f",e.values[i]));}sensorValues.put(e.sensor.getType(),b.toString());TextView v=sensorViews.get(e.sensor.getType());if(v!=null)v.setText(e.sensor.getName()+" · "+e.sensor.getVendor()+"\n"+b+" "+(e.sensor.getType()==Sensor.TYPE_ACCELEROMETER||e.sensor.getType()==Sensor.TYPE_LINEAR_ACCELERATION?"m/s²":e.sensor.getType()==Sensor.TYPE_GYROSCOPE?"rad/s":""));}public void onAccuracyChanged(Sensor s,int a){}};
 private String switchingEstimate(){double cpu=0;for(float x:cpuUse.values())cpu+=x;cpu=cpuUse.size()>0?cpu/cpuUse.size():0;String f=read("/sys/devices/system/cpu/cpu7/cpufreq/scaling_cur_freq");long hz=number(f);double freq=hz>0?hz/1000.0:0;double gpuLoad=0;String g=read("/sys/class/devfreq/13000000.mali/load");try{gpuLoad=Double.parseDouble(g.replace("%","").trim());}catch(Exception ignored){}double index=Math.min(100,cpu*0.7+gpuLoad*0.3);return String.format(Locale.US,"Estimated switching activity index: %.1f / 100\nCPU aggregate activity: %.1f%%\nBig-cluster clock sample: %s\nGPU driver load sample: %s\nMethod: normalized CPU utilization + available GPU utilization proxy\nPhysical transistor on/off states: NOT READABLE from Android",index,cpu,freq>0?String.format(Locale.US,"%.0f MHz",freq):"N/A",g);}
 private void sampleAll(){
  sampleCpu();set("switching",switchingEstimate());set("gpu",gpuInfo());set("memory",memoryInfo());set("storage",storageInfo());set("devfreq",devfreqInfo());set("network",networkInfo());set("power",powerInfo());set("thermal",thermalInfo());set("display",displayInfo());set("gnss",gpsText());status.setText("LIVE • sampled "+new java.text.SimpleDateFormat("HH:mm:ss",Locale.US).format(new Date())+" • "+Runtime.getRuntime().availableProcessors()+" logical CPUs");
 }
 private void set(String key,String s){TextView v=value(key);if(v!=null)v.setText(s);}
 private String gpsText(){return "GPS enabled: "+safeGpsEnabled()+"\nGNSS satellites: "+satellites+" · used in fix: "+usedSatellites+"\nAverage C/N0: "+String.format(Locale.US,"%.1f dB-Hz",avgCn0)+"\n"+(gpsActive?"Monitoring active":"Tap START GNSS MONITOR to request location permission and start GNSS callbacks");}
 private String safeGpsEnabled(){try{return String.valueOf(locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER));}catch(Exception e){return "N/A";}}
 private void startGnss(){
  if(checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)!=PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION,Manifest.permission.ACCESS_COARSE_LOCATION},41);return;}
  try{gpsActive=true;if(Build.VERSION.SDK_INT>=24){gnssCallback=new GnssStatus.Callback(){public void onSatelliteStatusChanged(GnssStatus s){satellites=s.getSatelliteCount();int used=0;float sum=0;for(int i=0;i<satellites;i++){if(s.usedInFix(i))used++;sum+=s.getCn0DbHz(i);}usedSatellites=used;avgCn0=satellites>0?sum/satellites:0;set("gnss",gpsText());}};if(Build.VERSION.SDK_INT>=30)locationManager.registerGnssStatusCallback(getMainExecutor(),gnssCallback);else locationManager.registerGnssStatusCallback(gnssCallback);}
   locationListener=new LocationListener(){public void onLocationChanged(Location l){set("gnss",gpsText()+"\nFIX: "+String.format(Locale.US,"%.6f, %.6f · accuracy %.1f m · age 0 s",l.getLatitude(),l.getLongitude(),l.getAccuracy()));}public void onProviderEnabled(String p){}public void onProviderDisabled(String p){}};
   locationManager.requestLocationUpdates(LocationManager.GPS_PROVIDER,1000,0,locationListener);set("gnss",gpsText()+"\nWaiting for satellite fix…");
  }catch(Exception e){gpsActive=false;set("gnss","GNSS error: "+e.getMessage());}
 }
 @Override public void onRequestPermissionsResult(int r,String[] p,int[] g){super.onRequestPermissionsResult(r,p,g);if(r==41&&g.length>0&&g[0]==PackageManager.PERMISSION_GRANTED)startGnss();}
 private void runCpuTest(){status.setText("CPU benchmark running…");worker.execute(()->{String out=runBenchmark(Runtime.getRuntime().availableProcessors(),8000000L);ui.post(()->{benchmark.setText(out);status.setText("CPU benchmark completed");});});}
 private static class LoadRenderer implements GLSurfaceView.Renderer{volatile boolean enabled=false;int program,pos,timeLoc;final java.nio.FloatBuffer vertices=java.nio.ByteBuffer.allocateDirect(32).order(java.nio.ByteOrder.nativeOrder()).asFloatBuffer();public void onSurfaceCreated(javax.microedition.khronos.opengles.GL10 g,javax.microedition.khronos.egl.EGLConfig c){String vs="attribute vec2 aPos;void main(){gl_Position=vec4(aPos,0.,1.);}";String fs="precision highp float;void main(){vec2 p=gl_FragCoord.xy/512.;float z=0.;for(int i=0;i<80;i++){p=abs(p)/max(dot(p,p),.02)-.7;z+=sin(p.x*8.)*cos(p.y*9.);}gl_FragColor=vec4(.5+.5*sin(z),.5+.5*cos(z),.4,1.);}";int v=sh(35633,vs),f=sh(35632,fs);program=GLES20.glCreateProgram();GLES20.glAttachShader(program,v);GLES20.glAttachShader(program,f);GLES20.glLinkProgram(program);pos=GLES20.glGetAttribLocation(program,"aPos");vertices.put(new float[]{-1,-1,1,-1,-1,1,1,1}).position(0);}int sh(int t,String s){int x=GLES20.glCreateShader(t);GLES20.glShaderSource(x,s);GLES20.glCompileShader(x);return x;}public void onSurfaceChanged(javax.microedition.khronos.opengles.GL10 g,int w,int h){GLES20.glViewport(0,0,w,h);}public void onDrawFrame(javax.microedition.khronos.opengles.GL10 g){if(!enabled){GLES20.glClearColor(.03f,.05f,.08f,1);GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT);return;}GLES20.glUseProgram(program);GLES20.glEnableVertexAttribArray(pos);GLES20.glVertexAttribPointer(pos,2,GLES20.GL_FLOAT,false,0,vertices);GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP,0,4);}}
 @Override protected void onPause(){super.onPause();if(gl!=null)gl.onPause();}
 @Override protected void onResume(){super.onResume();if(gl!=null)gl.onResume();}
 @Override protected void onDestroy(){ui.removeCallbacks(sampler);sensorManager.unregisterListener(sensorListener);if(gpsActive){try{if(locationListener!=null)locationManager.removeUpdates(locationListener);if(gnssCallback!=null&&Build.VERSION.SDK_INT>=24)locationManager.unregisterGnssStatusCallback(gnssCallback);}catch(Exception ignored){}}worker.shutdownNow();super.onDestroy();}
}