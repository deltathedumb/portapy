using PortaPy;

int calls = 0;

void helloWorld()
{
    Console.WriteLine("Hello, world!");
    calls += 1;
}

using (var env = new PortaPy.Environment())
{
    env.Add(helloWorld);
    env.Execute("helloWorld()\n");
}

if (calls != 1)
{
    throw new InvalidOperationException($"Expected one callback, observed {calls}.");
}

Console.WriteLine("csharp-managed-environment: ok");
