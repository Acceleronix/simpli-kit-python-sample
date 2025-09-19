from usr.libs.threading import Lock
from usr.libs.logging import getLogger
from usr import Qth
from usr.libs import CurrentApp
from . import lbs_service
logger = getLogger(__name__)


class QthClient(object):

    def __init__(self, app=None):
        self.opt_lock = Lock()
        if app:
            self.init_app(app)
    
    def __enter__(self):
        self.opt_lock.acquire()
        return self

    def __exit__(self, *args, **kwargs):
        self.opt_lock.release()

    def init_app(self, app):
        app.register("qth_client", self)
        Qth.init()
        Qth.setProductInfo(app.config["QTH_PRODUCT_KEY"], app.config["QTH_PRODUCT_SECRET"])
        Qth.setServer(app.config["QTH_SERVER"])
        Qth.setEventCb(
            {
                "devEvent": self.eventCallback, 
                "recvTrans": self.recvTransCallback, 
                "recvTsl": self.recvTslCallback, 
                "readTsl": self.readTslCallback, 
                "readTslServer": self.recvTslServerCallback,
                "ota": {
                    "otaPlan":self.otaPlanCallback,
                    "fotaResult":self.fotaResultCallback
                }
            }
        )
        logger.info(app.config["APP_version"])
        Qth.setAppVer(app.config["APP_version"], self.App_appResultCb)
    
    def load(self):
        self.start()

    def start(self):
        with self.opt_lock:
            if not Qth.state():
                logger.info("Starting QTH connection")
                Qth.start()
            else:
                logger.debug("QTH connection already active")
    
    def stop(self):
        with self.opt_lock:
            if Qth.state():
                logger.info("Stopping QTH connection")
                Qth.stop()
            else:
                logger.debug("QTH connection already stopped")
    def sendTsl(self, mode, value):
        return Qth.sendTsl(mode, value)

    def isStatusOk(self):
        return Qth.state()

    def sendLbs(self, lbs_data):
        return Qth.sendOutsideLocation(lbs_data)
    
    def sendGnss(self, nmea_data):
        return Qth.sendOutsideLocation(nmea_data)

    def eventCallback(self, event, result):
        logger.info("dev event:{} result:{}".format(event, result))
        if(2== event and 0 == result):
            Qth.otaRequest()

    def recvTransCallback(self, value):
        ret = Qth.sendTrans(1, value)
        logger.info("recvTrans value:{} ret:{}".format(value, ret))

    def recvTslCallback(self, value):
        with self.opt_lock:
            logger.info("recvTsl:{}".format(value))
            for cmdId, val in value.items():
                logger.info("recvTsl {}:{}".format(cmdId, val))
                
                # Handle fan control commands
                if cmdId == 11:  # Fan switch control
                    try:
                        fan_service = CurrentApp().fan_service
                        logger.info("Raw fan switch value: {} (type: {})".format(val, type(val)))
                        success = fan_service.set_fan_switch(bool(val))
                        logger.info("Fan switch command: {} (converted to: {}) - {}".format(val, bool(val), "Success" if success else "Failed"))
                    except Exception as e:
                        logger.error("Failed to process fan switch command: {}".format(e))
                        
                elif cmdId == 12:  # Fan mode control
                    try:
                        fan_service = CurrentApp().fan_service
                        success = fan_service.set_fan_mode(int(val))
                        logger.info("Fan mode command: {} - {}".format(val, "Success" if success else "Failed"))
                    except Exception as e:
                        logger.error("Failed to process fan mode command: {}".format(e))
                        
                elif cmdId == 13:  # Buzzer switch control
                    try:
                        buzzer_service = CurrentApp().buzzer_service
                        success = buzzer_service.set_buzzer_switch(bool(val))
                        logger.info("Buzzer switch command: {} - {}".format(val, "Success" if success else "Failed"))
                    except Exception as e:
                        logger.error("Failed to process buzzer switch command: {}".format(e))
    def readTslCallback(self, ids, pkgId):
        logger.info("readTsl ids:{} pkgId:{}".format(ids, pkgId))
        value = dict()
        
        # Get sensor data with hot-plug support
        temp1, humi = None, None
        try:
            temp1, humi = CurrentApp().sensor_service.get_temp1_and_humi()
        except Exception as e:
            pass
        
        press, temp2 = None, None
        try:
            press, temp2 = CurrentApp().sensor_service.get_press_and_temp2()
        except Exception as e:
            pass
        
        # TCS34725 color sensor data reporting disabled
        # r, g, b = None, None, None
        # try:
        #     r, g, b = CurrentApp().sensor_service.get_rgb888()
        # except Exception as e:
        #     pass

        accel, gyro = None, None
        try:
            accel, gyro = CurrentApp().sensor_service.get_accel_gyro()
        except Exception as e:
            pass

        # Get fan status
        fan_status = None
        try:
            fan_status = CurrentApp().fan_service.get_fan_status()
        except Exception as e:
            pass

        # Get buzzer status
        buzzer_status = None
        try:
            buzzer_status = CurrentApp().buzzer_service.get_buzzer_status()
        except Exception as e:
            pass

        # Build response based on requested IDs and data availability
        for id in ids:
            if id == 3 and temp1 is not None:
                value[3] = temp1
            elif id == 4 and humi is not None:
                value[4] = humi
            elif id == 5 and temp2 is not None:
                value[5] = temp2
            elif id == 6 and press is not None:
                value[6] = press
            # TCS34725 color sensor data reporting disabled
            # elif id == 7 and r is not None and g is not None and b is not None:
            #     value[7] = {1: r, 2: g, 3: b}
            elif id == 9 and gyro is not None:
                value[9] = {1: CurrentApp().sensor_service.round_if_needed(gyro[0]), 2: CurrentApp().sensor_service.round_if_needed(gyro[1]), 3: CurrentApp().sensor_service.round_if_needed(gyro[2])}
            elif id == 10 and accel is not None:
                value[10] = {1: CurrentApp().sensor_service.round_if_needed(accel[0]), 2: CurrentApp().sensor_service.round_if_needed(accel[1]), 3: CurrentApp().sensor_service.round_if_needed(accel[2])}
            elif id == 11 and fan_status is not None:
                value[11] = fan_status['switch']
            elif id == 12 and fan_status is not None:
                value[12] = fan_status['mode']
            elif id == 13 and buzzer_status is not None:
                value[13] = buzzer_status['switch']
            else:
                pass

        # LBS service
        try:
            lbs = lbs_service.LbsService()
            lbs.put_lbs()
        except Exception as e:
            pass

        Qth.ackTsl(1, value, pkgId)
       
        
    def recvTslServerCallback(self, serverId, value, pkgId):
        logger.info("recvTslServer serverId:{} value:{} pkgId:{}".format(serverId, value, pkgId))
        Qth.ackTslServer(1, serverId, value, pkgId)

    def otaPlanCallback(self, plans):
        logger.info("otaPlan:{}".format(plans))
        Qth.otaAction(1)

    def fotaResultCallback(self, comp_no, result):
        logger.info("fotaResult comp_no:{} result:{}".format(comp_no, result))
        
    def sotaInfoCallback(self, comp_no, version, url, md5, crc):
        logger.info("sotaInfo comp_no:{} version:{} url:{} md5:{} crc:{}".format(comp_no, version, url, md5, crc))
        # 当使用url下载固件完成，且MCU更新完毕后，需要获取MCU最新的版本信息，并通过setMcuVer进行更新
        Qth.setMcuVer("MCU1", "V1.0.0", self.sotaInfoCallback, self.sotaResultCallback)

    def sotaResultCallback(self, comp_no, result):
        logger.info("sotaResult comp_no:{} result:{}".format(comp_no, result))

    def App_appResultCb(self, comp_no, result):
        global Appcode_version
        logger.debug('appResult:',comp_no, result)