#include <Wire.h>
#include <UnoWiFiDevEd.h>

#define CONNECTOR "mqtt"
#define TOPIC "arduino/analog/A1"

void setup() {
	Ciao.begin();
}


void loop(){

	delay(5000);
	int data_value = analogRead(A1); // data value from analog pin 1
	Ciao.write(CONNECTOR, TOPIC, String(data_value)); // pushes data into a channel called PIN_A1

}
