#include <Arduino.h>
#include <Wire.h>
#include <Servo.h>

uint8_t hexVal(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'A' && c <= 'F') return 10 + (c - 'A');
  if (c >= 'a' && c <= 'f') return 10 + (c - 'a');
  return 0xFF;
}

uint8_t crc8(const String &payload) {
  const char *p = payload.c_str();
  uint16_t s = 0;
  for (size_t i = 0; i < payload.length(); ++i)
    s = (s + (uint8_t)p[i]) & 0xFFFF;
  return (uint8_t)(s & 0xFF);
}

int findSep(const String &s) {
  for (int i = s.length() - 1; i >= 0; --i)
    if (s[i] == '|') return i;
  return -1;
}

bool isValidEcho(const String &u) {
  return u.startsWith("ECHO(") && u.endsWith(")");
}

bool isValidMRV(const String &u) {
  if (u.length() < 4) return false;
  char c = u[0];
  if (!(c == 'M' || c == 'R' || c == 'V')) return false;
  int lp = u.indexOf('(');
  if (lp != 1) return false;
  if (u[u.length() - 1] != ')') return false;
  if (u.length() == 3) return false;
  return true;
}

String rx;

unsigned long myTime;
Servo myservo;
float distance;
float kp = 3.0;
float ki = 2.0;
float kd = 1.5;
float integral = 0.0;
float derivative = 0.0;
float previousError = 0.0;
float distance_point = 26.5;
int servo_zero = 90;
int t = 100;
float lastOutput = 0.0;
float lastError = 0.0;

enum Mode {
  MODE_IDLE = 0,
  MODE_TEST,
  MODE_RUN,
  MODE_HOLD
};

Mode mode = MODE_IDLE;
unsigned long runStartTime = 0;
unsigned long holdStartTime = 0;
float maeSum = 0.0;
unsigned long maeCount = 0;

float get_dist(int n) {
  long sum = 0;
  for (int i = 0; i < n; i++) {
    sum += analogRead(A0);
  }
  float adc = (float)sum / n;
  float distance_cm = 17569.7 * pow(adc, -1.2062);
  return distance_cm;
}

void PID_step() {
  float proportional = distance - distance_point;
  integral = integral + proportional * 0.1;
  derivative = (proportional - previousError) / 0.1;
  float output = kp * proportional + ki * integral + kd * derivative;
  previousError = proportional;
  lastOutput = output;
  lastError = proportional;
  int cmd = servo_zero + (int)output;
  if (cmd < 0) cmd = 0;
  if (cmd > 180) cmd = 180;
  myservo.write(cmd);
}

void run_test_mode() {
  PID_step();
  Serial.print(F("TEL;dist="));
  Serial.print(distance, 2);
  Serial.print(F(";sp="));
  Serial.print(distance_point, 2);
  Serial.print(F(";err="));
  Serial.print(lastError, 2);
  Serial.print(F(";out="));
  Serial.print(lastOutput, 2);
  Serial.print(F("\r\n"));
}

void run_run_mode() {
  unsigned long now = millis();
  unsigned long elapsed = now - runStartTime;
  PID_step();
  if (elapsed >= 10000UL) {
    maeSum = 0.0;
    maeCount = 0;
    holdStartTime = millis();
    mode = MODE_HOLD;
  }
  if (elapsed >= 15000UL) {
    float mae = (maeCount > 0) ? maeSum / (float)maeCount : 0.0;
    Serial.print(F("MAE="));
    Serial.print(mae, 2);
    Serial.print(F("\r\n"));
    myservo.write(servo_zero);
    mode = MODE_IDLE;
  }
}

void run_hold_mode() {
  float e = fabs(distance - distance_point);
  maeSum += e;
  maeCount++;
  unsigned long now = millis();
  if (now - holdStartTime >= 3000UL) {
    float mae = (maeCount > 0) ? maeSum / (float)maeCount : 0.0;
    Serial.print(F("MAE="));
    Serial.print(mae, 2);
    Serial.print(F("\r\n"));
    myservo.write(servo_zero);
    mode = MODE_IDLE;
  }
}

void handleKnownSimple(const String &up, const String &payload) {
  if (up == "PING") {
    Serial.println(F("PONG"));
    return;
  }
  if (isValidEcho(up)) {
    int lp = payload.indexOf('(');
    int rp = payload.lastIndexOf(')');
    if (lp >= 0 && rp > lp) {
      String text = payload.substring(lp + 1, rp);
      Serial.println(text);
      return;
    }
  }
  if (up == "S" || up == "I" || up == "B" || up == "STOP" || isValidMRV(up)) {
    if (up == "B" || up == "STOP") {
      mode = MODE_IDLE;
      myservo.write(servo_zero);
    }
    Serial.println(F("ACK"));
    return;
  }
  Serial.println(F("NACK(UNKNOWN_CMD)"));
}

void handlePIDCommand(const String &payload) {
  String inside = payload.substring(4, payload.length() - 1);
  int c1 = inside.indexOf(',');
  int c2 = inside.indexOf(',', c1 + 1);
  if (c1 == -1 || c2 == -1) {
    Serial.println(F("NACK(BAD_PID_ARGS)"));
    return;
  }
  String sKp = inside.substring(0, c1);
  String sKi = inside.substring(c1 + 1, c2);
  String sKd = inside.substring(c2 + 1);
  kp = sKp.toFloat();
  ki = sKi.toFloat();
  kd = sKd.toFloat();
  integral = 0.0;
  previousError = 0.0;
  Serial.println(F("ACK"));
}

void handleTARGETCommand(const String &payload) {
  String val = payload.substring(7, payload.length() - 1);
  distance_point = val.toFloat();
  integral = 0.0;
  previousError = 0.0;
  Serial.println(F("ACK"));
}

void handleZEROCommand(const String &payload) {
  String val = payload.substring(5, payload.length() - 1);
  servo_zero = val.toInt();
  myservo.write(servo_zero);
  Serial.println(F("ACK"));
}

void handleTESTCommand() {
  mode = MODE_TEST;
  integral = 0.0;
  previousError = 0.0;
  Serial.println(F("ACK"));
}

void handleSTARTCommand() {
  myservo.write(servo_zero + 5);
  integral = 0.0;
  previousError = 0.0;
  runStartTime = millis();
  mode = MODE_RUN;
  Serial.println(F("ACK"));
}

void handleLine(const String &line) {
  String s = line;
  if (s.endsWith("\n")) s.remove(s.length() - 1);
  if (s.endsWith("\r")) s.remove(s.length() - 1);
  if (s.length() == 0) {
    Serial.println(F("NACK(EMPTY)"));
    return;
  }
  int k = findSep(s);
  if (k < 0) {
    Serial.println(F("NACK(CRC_MISSING)"));
    return;
  }
  String payload = s.substring(0, k);
  String crcTxt = s.substring(k + 1);
  if (crcTxt.length() < 2) {
    Serial.println(F("NACK(CRC_MISSING)"));
    return;
  }
  uint8_t hi = hexVal(crcTxt[0]), lo = hexVal(crcTxt[1]);
  if (hi == 0xFF || lo == 0xFF) {
    Serial.println(F("NACK(CRC_BADHEX)"));
    return;
  }
  uint8_t crcRx = (uint8_t)((hi << 4) | lo);
  uint8_t crcCalc = crc8(payload);
  if (crcRx != crcCalc) {
    Serial.println(F("NACK(CRC_FAIL)"));
    return;
  }
  String up = payload;
  up.toUpperCase();
  if (up.startsWith("TARGET(") && up.endsWith(")")) { handleTARGETCommand(payload); return; }
  if (up.startsWith("PID(") && up.endsWith(")"))    { handlePIDCommand(payload); return; }
  if (up.startsWith("ZERO(") && up.endsWith(")"))   { handleZEROCommand(payload); return; }
  if (up == "TEST")  { handleTESTCommand(); return; }
  if (up == "START") { handleSTARTCommand(); return; }
  if (up == "STOP")  { mode = MODE_IDLE; myservo.write(servo_zero); Serial.println(F("ACK")); return; }
  handleKnownSimple(up, payload);
}

void setup() {
  Serial.begin(9600);
  rx.reserve(256);
  myservo.attach(9);
  myservo.write(95);
  pinMode(A0, INPUT);
  myTime = millis();
  mode = MODE_IDLE;
  Serial.println(F("READY"));
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    rx += c;
    if (c == '\n') {
      handleLine(rx);
      rx = "";
    }
  }
  if (rx.length() > 512) {
    rx = "";
    Serial.println(F("NACK(OVERFLOW)"));
  }
  unsigned long now = millis();
  if (now > myTime + t) {
    distance = get_dist(100);
    myTime = now;
    if (mode == MODE_TEST)      run_test_mode();
    else if (mode == MODE_RUN)  run_run_mode();
    else if (mode == MODE_HOLD) run_hold_mode();
  }
}
