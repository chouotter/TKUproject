#include <Arduino.h>

#define ID_ERROR		String(-1)
#define ID_EMPTY		String(0)
#define ID_READY		String(1)
#define END_TX_CHAR		(char)4
#define DATA_SPLIT_CHAR	(char)30
#define ID_SIZE_TX		25

class CiaoData {
	public:

		const char* msg_split[3];

		const char* get(int index){
			return msg_split[index];
		}

		bool isEmpty(){
			//if (atoi( get(1) ) > 0)
			//if (get(2) != "")
			if ( strncmp(get(2), "", 1) != 0)
				return false;
			else
				return true;
		}
};
