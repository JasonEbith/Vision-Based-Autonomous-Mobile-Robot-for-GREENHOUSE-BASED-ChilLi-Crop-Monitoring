#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

// ── Motor direction pins ─────────────────────────────────────
int IN1 = 13, IN2 = 12;   // BL
int IN3 = 14, IN4 = 27;   // BR
int IN5 = 26, IN6 = 25;   // FR
int IN7 = 33, IN8 = 32;   // FL

// ── PWM (enable) pins ────────────────────────────────────────
int ENA1 = 4,  ENB1 = 5;
int ENA2 = 18, ENB2 = 19;

// ── Motor tuning ─────────────────────────────────────────────
int maxLimit  = 80;
int accelStep = 8;
int deadband  = 8;

// ── Turn mode ────────────────────────────────────────────────
String turnMode = "ARC";

// ── Motor ramp state ─────────────────────────────────────────
int currentLeft  = 0;
int currentRight = 0;
int targetLeft   = 0;
int targetRight  = 0;

// ── Servo config ─────────────────────────────────────────────
#define SERVOMIN       120
#define SERVOMAX       600

// Channel 0 — Pan servo (NEW)
// ROW mode  → 90°  (looking straight ahead / centred)
// PEST mode → 0°   (rotated to scan position)
#define PAN_CHANNEL    0
#define PAN_ROW_ANGLE  50
#define PAN_PEST_ANGLE  0

// Channel 1 — Tilt servo (existing)
#define TILT_CHANNEL   1
int currentTiltAngle = 60;
int currentPanAngle  = 90;

// ════════════════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);

  pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT);
  pinMode(IN5, OUTPUT); pinMode(IN6, OUTPUT);
  pinMode(IN7, OUTPUT); pinMode(IN8, OUTPUT);

  ledcAttach(ENA1, 1000, 8);
  ledcAttach(ENB1, 1000, 8);
  ledcAttach(ENA2, 1000, 8);
  ledcAttach(ENB2, 1000, 8);

  applyMotors(0, 0);

  Wire.begin();
  pwm.begin();
  pwm.setPWMFreq(50);
  delay(100);

  // Init both servos to ROW positions
  setPan(PAN_ROW_ANGLE);
  setTilt(50);

  Serial.println("ESP32 ready. TurnMode=" + turnMode);
}

// ════════════════════════════════════════════════════════════
//  SERVO HELPERS
// ════════════════════════════════════════════════════════════
int angleToPulse(int angle) {
  return map(angle, 0, 180, SERVOMIN, SERVOMAX);
}

// Channel 1 — tilt (controlled by Pi via "tilt:N")
void setTilt(int angle) {
  angle = constrain(angle, 0, 180);
  pwm.setPWM(TILT_CHANNEL, 0, angleToPulse(angle));
  currentTiltAngle = angle;
}

// Channel 0 — pan (controlled by Pi via "pan:N" or "mode:PEST"/"mode:ROW")
void setPan(int angle) {
  angle = constrain(angle, 0, 180);
  pwm.setPWM(PAN_CHANNEL, 0, angleToPulse(angle));
  currentPanAngle = angle;
}

// ════════════════════════════════════════════════════════════
//  MOTOR — corrected wheel mapping
//  LEFT  side: FL = IN3/IN4 (ENB1) + BL = IN7/IN8 (ENB2)
//  RIGHT side: FR = IN1/IN2 (ENA1) + BR = IN5/IN6 (ENA2)
// ════════════════════════════════════════════════════════════
void applyMotors(int L, int R) {
  // LEFT side (FL + BL)
  if (L > 0) {
    digitalWrite(IN3, LOW);  digitalWrite(IN4, HIGH);  // FL fwd
    digitalWrite(IN7, LOW);  digitalWrite(IN8, HIGH);  // BL fwd
  } else if (L < 0) {
    digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);   // FL rev
    digitalWrite(IN7, HIGH); digitalWrite(IN8, LOW);   // BL rev
  } else {
    digitalWrite(IN3, LOW);  digitalWrite(IN4, LOW);
    digitalWrite(IN7, LOW);  digitalWrite(IN8, LOW);
  }
  // RIGHT side (FR + BR)
  if (R > 0) {
    digitalWrite(IN1, LOW);  digitalWrite(IN2, HIGH);  // FR fwd
    digitalWrite(IN5, LOW);  digitalWrite(IN6, HIGH);  // BR fwd
  } else if (R < 0) {
    digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);   // FR rev
    digitalWrite(IN5, HIGH); digitalWrite(IN6, LOW);   // BR rev
  } else {
    digitalWrite(IN1, LOW);  digitalWrite(IN2, LOW);
    digitalWrite(IN5, LOW);  digitalWrite(IN6, LOW);
  }
  ledcWrite(ENB1, abs(L));   // FL
  ledcWrite(ENB2, abs(L));   // BL
  ledcWrite(ENA1, abs(R));   // FR
  ledcWrite(ENA2, abs(R));   // BR
}

int rampStep(int current, int target) {
  int diff = target - current;
  if (abs(diff) <= accelStep) return target;
  return current + (diff > 0 ? accelStep : -accelStep);
}

void setMotors(int L, int R) {
  if (abs(L) < deadband) L = 0;
  if (abs(R) < deadband) R = 0;
  targetLeft  = constrain(L, -maxLimit, maxLimit);
  targetRight = constrain(R, -maxLimit, maxLimit);
}

void setMotorsSpot(int L, int R) {
  if (abs(L) < deadband) L = 0;
  if (abs(R) < deadband) R = 0;
  int diff = L - R;
  if (abs(diff) < 20) {
    int spd = (L + R) / 2;
    targetLeft  = constrain(spd, -maxLimit, maxLimit);
    targetRight = constrain(spd, -maxLimit, maxLimit);
  } else if (diff > 0) {
    targetLeft  =  maxLimit;
    targetRight = -maxLimit;
  } else {
    targetLeft  = -maxLimit;
    targetRight =  maxLimit;
  }
}

void stopMotors() {
  targetLeft = targetRight = 0;
  currentLeft = currentRight = 0;
  applyMotors(0, 0);
}

// ════════════════════════════════════════════════════════════
//  loop
// ════════════════════════════════════════════════════════════
void loop() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "forward") {
      setMotors(maxLimit, maxLimit);
      Serial.println("OK: forward");

    } else if (cmd == "backward") {
      setMotors(-maxLimit, -maxLimit);
      Serial.println("OK: backward");

    } else if (cmd == "stop") {
      stopMotors();
      Serial.println("OK: stop");

    } else if (cmd == "left") {
      setMotors(-maxLimit, maxLimit);
      Serial.println("OK: spin left");

    } else if (cmd == "right") {
      setMotors(maxLimit, -maxLimit);
      Serial.println("OK: spin right");

    } else if (cmd.startsWith("move:")) {
      int comma = cmd.indexOf(',');
      if (comma > 5) {
        int L = cmd.substring(5, comma).toInt();
        int R = cmd.substring(comma + 1).toInt();
        if (turnMode == "SPOT") setMotorsSpot(L, R);
        else                    setMotors(L, R);
        Serial.println("OK: move " + String(L) + "," + String(R)
                       + " [" + turnMode + "]");
      } else {
        Serial.println("ERR: bad move format");
      }

    } else if (cmd.startsWith("tilt:")) {
      // Channel 1 — tilt servo
      int angle = cmd.substring(5).toInt();
      setTilt(angle);
      Serial.println("OK: tilt " + String(angle));

    } else if (cmd.startsWith("pan:")) {
      // Channel 0 — pan servo (explicit angle)
      int angle = cmd.substring(4).toInt();
      setPan(angle);
      Serial.println("OK: pan " + String(angle));

    } else if (cmd == "mode:PEST") {
      // Switch to PEST: pan servo → 0°
      turnMode = "PEST";
      setPan(PAN_PEST_ANGLE);
      Serial.println("OK: PEST mode — pan=" + String(PAN_PEST_ANGLE) + "deg");

    } else if (cmd == "mode:ROW") {
      // Switch to ROW: pan servo → 90°
      turnMode = "ARC";
      setPan(PAN_ROW_ANGLE);
      Serial.println("OK: ROW mode — pan=" + String(PAN_ROW_ANGLE) + "deg");

    } else if (cmd == "mode:SPOT") {
      turnMode = "SPOT";
      Serial.println("OK: turnMode=SPOT");

    } else if (cmd == "mode:ARC") {
      turnMode = "ARC";
      Serial.println("OK: turnMode=ARC");

    } else {
      Serial.println("ERR: unknown command: " + cmd);
    }
  }

  currentLeft  = rampStep(currentLeft,  targetLeft);
  currentRight = rampStep(currentRight, targetRight);
  applyMotors(currentLeft, currentRight);

  delay(20);
}
