#include <Servo.h>

Servo gripServo;


const uint8_t EN_PINS[4] = {A0, A1, A2, A3};

struct Motor {
  uint8_t stepPin;
  uint8_t dirPin;
  unsigned int highDelay;
  unsigned int lowDelay;
  unsigned long lastMicros;
  bool stepState;
  bool active;
};

Motor motors[4] = {
  {2, 3, 2000, 2000, 0, false, false},
  {4, 5, 2000, 2000, 0, false, false},
  {6, 7, 2000, 2000, 0, false, false},
  {8, 9, 2000, 2000, 0, false, false}
};

bool holdEnabled = true;
unsigned long lastCmdTime = 0;
String inputBuffer = "";

void setup() {
  Serial.begin(115200);

  for (int i = 0; i < 4; i++) {
    pinMode(EN_PINS[i], OUTPUT);
    digitalWrite(EN_PINS[i], HIGH); // HIGH = активен по умолчанию
    pinMode(motors[i].stepPin, OUTPUT);
    pinMode(motors[i].dirPin, OUTPUT);
    digitalWrite(motors[i].stepPin, LOW);
  }

  gripServo.attach(10);
  gripServo.write(90);

  Serial.println("READY");
}

void setHold(bool enable) {
  holdEnabled = enable;
  for (int i = 0; i < 4; i++) {
    if (!motors[i].active) {
      // удержание ВКЛ -> HIGH (активен), ВЫКЛ -> LOW (отключён)
      digitalWrite(EN_PINS[i], enable ? HIGH : LOW);
    }
  }
}

void updateMotor(int m) {
  if (!motors[m].active) return;

  unsigned long now = micros();
  unsigned long elapsed = now - motors[m].lastMicros;

  if (motors[m].stepState) {
    if (elapsed >= motors[m].highDelay) {
      digitalWrite(motors[m].stepPin, LOW);
      motors[m].stepState = false;
      motors[m].lastMicros = now;
    }
  } else {
    if (elapsed >= motors[m].lowDelay) {
      digitalWrite(motors[m].stepPin, HIGH);
      motors[m].stepState = true;
      motors[m].lastMicros = now;
    }
  }
}

void startMotor(int m, bool dir) {
  if (m < 0 || m > 3) return;
  digitalWrite(EN_PINS[m], HIGH); // HIGH = активен
  digitalWrite(motors[m].dirPin, dir);
  motors[m].active = true;
  motors[m].lastMicros = micros();
}

void stopMotor(int m) {
  if (m < 0 || m > 3) return;
  motors[m].active = false;
  digitalWrite(motors[m].stepPin, LOW);
  if (!holdEnabled) {
    digitalWrite(EN_PINS[m], LOW); // LOW = отключён (ток снят)
  }
  // если holdEnabled = true — оставляем HIGH (мотор держит позицию)
}

void checkTimeout() {
  if (millis() - lastCmdTime > 150) {
    for (int i = 0; i < 4; i++) {
      if (motors[i].active) stopMotor(i);
    }
  }
}

void processCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;

  lastCmdTime = millis();

  char c = cmd.charAt(0);
  int motorNum = -1;

  if (cmd.length() > 1) {
    char n = cmd.charAt(1);
    if (n >= '1' && n <= '4') motorNum = n - '1';
  }

  int colonPos = cmd.indexOf(':');
  int value = 0;
  if (colonPos > 0) value = cmd.substring(colonPos + 1).toInt();

  if      (c == 'U' && motorNum >= 0) startMotor(motorNum, HIGH);
  else if (c == 'D' && motorNum >= 0) startMotor(motorNum, LOW);
  else if (c == 'W') { for (int i = 0; i < 4; i++) startMotor(i, HIGH); }
  else if (c == 'Z') { for (int i = 0; i < 4; i++) startMotor(i, LOW);  }
  else if (c == 'X') {
    for (int i = 0; i < 4; i++) stopMotor(i);
    Serial.println("STOP");
  }
  else if (c == 'E') {
    setHold(cmd.charAt(1) == '1');
  }
  else if (c == 'S' && cmd.length() > 1) {
    char d = cmd.charAt(1);
    if      (d == 'R') gripServo.write(0);
    else if (d == 'L') gripServo.write(180);
    else if (d == 'S') gripServo.write(90);
  }
  else if (c == 'H' && motorNum >= 0 && colonPos > 0)
    motors[motorNum].highDelay = constrain(value, 50, 5000);
  else if (c == 'L' && motorNum >= 0 && colonPos > 0)
    motors[motorNum].lowDelay  = constrain(value, 50, 5000);
  else if (c == '?') {
    for (int i = 0; i < 4; i++) {
      Serial.print("M"); Serial.print(i + 1);
      Serial.print(" H:"); Serial.print(motors[i].highDelay);
      Serial.print(" L:"); Serial.print(motors[i].lowDelay);
      if (i < 3) Serial.print(" | ");
    }
    Serial.println();
  }
}

void loop() {
  updateMotor(0);
  updateMotor(1);
  updateMotor(2);
  updateMotor(3);

  checkTimeout();

  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n') {
      processCommand(inputBuffer);
      inputBuffer = "";
    } else {
      inputBuffer += ch;
    }
  }
}