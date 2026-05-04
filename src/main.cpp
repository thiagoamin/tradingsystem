#include "ibkr_wrapper/IbkrClient.h"

int main()
{
    IbkrClient client;
    const char *host = "127.0.0.1";
    int port = 7497;
    int clientId = 0;

    client.connect(host, port, clientId);

    for (;;)
    {

        while (client.isConnected())
        {
        }
    }

    return 0;
}