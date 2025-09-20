#include <Wire.h>
#include <UnoWiFiDevEd.h>

#define CONNECTOR "mqtt"
#define TOPIC "arduino/data"

void setup() {
	Ciao.begin();
	Serial.begin(9600);
}

void loop(){
	CiaoData data = Ciao.read(CONNECTOR, TOPIC);
	if (!data.isEmpty()){
		const char* value = data.get(2);
		Serial.println(value);
	}
}
