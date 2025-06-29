from parser.Parser import Parser
from runtime.Environment import Environment, create_global_env
from runtime.Interpreter import evaluate
from runtime.Types import NoneVal, NumberVal, StringVal

def console(show_tokens=False)->None:
    parser = Parser()
    env = create_global_env()

    print(">> W (V 0.1 ) -> ")
    if show_tokens:
        print("(Modo debug: mostrando tokens)")
    else:
        print("(Usa --tokens para ver tokens)")

    while True:
        try:
            text = input(">> ")
        except EOFError:
            break

        if not text:
            continue
        elif text == "exit":
            break

        program = parser.parse(text, show_tokens=show_tokens)
        
        res = evaluate(program, env)

        if res and hasattr(res, 'type') and res.type != 'None':
            print(res)


def from_file(file:str, show_tokens=False)->None:
    with open(file, "r") as f:
        text = f.read()

    parser = Parser()
    env = create_global_env()

    program = parser.parse(text, show_tokens=show_tokens)
    res = evaluate(program, env)

    if res and hasattr(res, 'type') and res.type != 'None':
        print(res)


def main() -> None:
    import sys
    
    show_tokens = False
    file_to_run = None
    
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--tokens" or arg == "-t":
            show_tokens = True
        elif arg == "--help" or arg == "-h":
            print("W Language Interpreter")
            print("Usage:")
            print("  python main.py                # Interactive mode")
            print("  python main.py <file>         # Run file")
            print("  python main.py --tokens <file>  # Run file with token output")
            print("  python main.py -t <file>      # Run file with token output (short)")
            return
        elif not arg.startswith("-"):
            file_to_run = arg
    
    if file_to_run:
        from_file(file_to_run, show_tokens)
    else:
        console(show_tokens)

if __name__ == '__main__':
    main()

