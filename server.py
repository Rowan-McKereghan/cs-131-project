import asyncio
import argparse
import time
import json
import aiohttp
import logging
import sys




portAlloc = '10480-10487' # the ports i was allocated on the school server to use (now closed)

# googleAPIkey = ''' the key that was allocated to us in class – costs real money to use '''

nameToPorts = {'Juzang': "10480", 'Bernard': "10481", 'Jaquez': "10482", 'Campbell': "10483", 'Clark': "10484"}

serverComms = {"Clark": ["Juzang", "Jaquez"],
               "Bernard": ["Juzang", "Jaquez", "Campbell"],
               "Juzang": ["Clark", "Campbell", "Bernard"],
               "Jaquez": ["Clark", "Bernard"],
               "Campbell": ["Bernard", "Juzang"]
              }

ip = '127.0.0.1'

logPrint = True


class Server:
    def __init__(self, name, port):
        self.name = name
        self.port = port
        self.ClientInfoForWHATSAT = dict()

    async def handle_connection(self, reader, writer):
        while(not reader.at_eof()):
            data = await reader.readline()
            message = data.decode()
            messageArr = message.split()
            if(message == ""):
                continue
            log("{} received {}".format(self.name, message))
            if(len(messageArr) == 4):
                if(messageArr[0] == 'IAMAT'):
                    if(not self.checkIAMAT(messageArr)):
                        sendback_message = '? {}'.format(message)
                    else:
                        timeDifference = time.time() - float(messageArr[3])
                        appender = '+' if timeDifference >= 0 else ''
                        sendback_message = "AT {} {} {} {} {}".format(self.name, appender+str(timeDifference), messageArr[1], messageArr[2], messageArr[3])
                        if((not messageArr[1] in self.ClientInfoForWHATSAT.keys()) or float(self.ClientInfoForWHATSAT[messageArr[1]].split()[5]) < float(messageArr[3])):
                            self.ClientInfoForWHATSAT[messageArr[1]] = sendback_message
                            await self.sendToNeighbors(sendback_message)
                elif(messageArr[0] == 'WHATSAT'):
                    if(not self.checkWHATSAT(messageArr)):
                        sendback_message = '? {}'.format(message)
                    else:
                        if messageArr[1] in self.ClientInfoForWHATSAT.keys():
                            oldMessage = self.ClientInfoForWHATSAT[messageArr[1]].split()
                            coordinates = oldMessage[4]
                            jsonStr = await self.placeRequest(self.returnURLCoords(coordinates), messageArr[2]) #call placeRequest here, figure out how to store coords
                            bound = int(messageArr[3])
                            jsonObj = json.loads(jsonStr)
                            if(len(jsonObj["results"]) > bound):
                                jsonObj["results"] = jsonObj["results"][0:bound]
                                jsonStr = json.dumps(jsonObj, indent=4)
                            sendback_message = "{}\n{}\n\n".format(self.ClientInfoForWHATSAT[messageArr[1]], str(jsonStr).rstrip('\n'))
                        else:
                            log("Error: No Prior AT or IAMAT")
                            sendback_message = '? {}'.format(message)
                else:
                    sendback_message = '? {}'.format(message)
            else:
                if(self.checkAT(messageArr)):
                    sendback_message = None
                    if(messageArr[3] in self.ClientInfoForWHATSAT.keys()):
                        oldAT = self.ClientInfoForWHATSAT[messageArr[3]]
                        temp = oldAT.split()
                        oldTime = float(temp[5])
                        if(float(messageArr[5]) > oldTime):
                            log("Updating client info for {}".format(messageArr[3]))
                            self.ClientInfoForWHATSAT[messageArr[3]] = message
                            await self.sendToNeighbors(message)
                        else:
                            log("Newer message already recieved and propagated")
                    else:
                        self.ClientInfoForWHATSAT[messageArr[3]] = message
                        await self.sendToNeighbors(message)
                else:
                    sendback_message = '? {}'.format(message)   
            if(sendback_message != None):
                log("{} sending: {}".format(self.name, sendback_message))
                writer.write(sendback_message.encode())
                await writer.drain()

        log("close the client socket")
        writer.close()


    async def sendToNeighbors(self, message):
        for server in serverComms[self.name]:
            try:
                log("Attempting connection to {}".format(server))
                reader, writer = await asyncio.open_connection(ip, nameToPorts[server])
                writer.write(message.encode())
                log("Connection succeeded, {} sends {} to {}".format(self.name, message, server))
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                log("Connection to {} closed".format(server))
            except:
                log("Connection to {} failed!".format(server))

    async def placeRequest(self, coordinates, radius):
        getURL = 'https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={0}&radius={1}&key={2}'.format(coordinates, radius, googleAPIkey)
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(
            ssl=False,
            ),
            ) as session:
            async with session.get(getURL) as response:
                return await response.text()

    def checkIAMAT(self, message):
        if(not self.checkFloat(message[3])):
            return False
        numStr = message[2].replace('-', '+')
        coordinates = numStr.split('+')
        while("" in coordinates):
            coordinates.remove("")
        if(len(coordinates) != 2 or not (self.checkFloat(coordinates[0]) and self.checkFloat(coordinates[1]))):
            return False
        return True

    def checkWHATSAT(self, message):
        if(not (self.checkFloat(message[2]) and message[3].isdigit())):
            return False
        if(float(message[2]) > 50 or float(message[2]) < 0):
            return False
        if(int(message[3]) > 20 or int(message[3]) < 0):
            return False
        return True

    def checkAT(self, message):
        if(len(message) != 6):
            return False
        if(message[0] != 'AT'):
            return False
        if(not(message[1] in nameToPorts.keys())):
            return False
        numStr = message[4].replace('-', '+')
        coordinates = numStr.split('+')
        while("" in coordinates):
            coordinates.remove("")
        if(len(coordinates) != 2 or not (self.checkFloat(coordinates[0]) and self.checkFloat(coordinates[1]))):
            return False
        if(not self.checkFloat(message[5])):
            return False
        return True
        
    def returnURLCoords(self, coordinates):
        temp1 = coordinates.replace("+", "~+")
        temp2 = temp1.replace('-', '~-')
        URLcoordList = temp2.split('~')
        while("" in URLcoordList):
            URLcoordList.remove("")
        return URLcoordList[0] + ',' + URLcoordList[1]

    def checkFloat(self, arg):
        try:
            float(arg)
            return True
        except ValueError:
            return False
    
    async def run_forever(self):
        server = await asyncio.start_server(self.handle_connection, ip, self.port)

        # Serve requests until Ctrl+C is pressed
        log(f'serving on {server.sockets[0].getsockname()}')
        async with server:
            await server.serve_forever()
        # Close the server
        server.close()



def main():
    parser = argparse.ArgumentParser('CS131 project example argument parser for server')
    parser.add_argument('server_name', type=str, help='required server name input')
    args = parser.parse_args()
    if(not args.server_name in nameToPorts.keys()):
        print("Server Does Not Exist!")
        sys.exit(1)
    logging.basicConfig(filename="{}.log".format(args.server_name), format='%(levelname)s: %(message)s', filemode='w+', level=logging.INFO)
    server = Server(args.server_name, nameToPorts[args.server_name])
    log("Hello, welcome to the logging file for server {}".format(args.server_name))
    try:
        asyncio.run(server.run_forever())
    except KeyboardInterrupt:
        pass

def log(msg):
    if logPrint == True:
        logging.info(msg)
    else:
        print(msg)


if __name__ == '__main__':
    main()


'''
async def main():
    server = await asyncio.start_server(handle_connection, host='127.0.0.1', port=12345)
    await server.serve_forever()
async def handle_connection(reader, writer):
    data = await reader.readline()
    name = data.decode()
    greeting = "Hello, " + name
    writer.write(greeting.encode())
    await writer.drain()
    writer.close()
if __name__ == '__main__':
    asyncio.run(main())'''

