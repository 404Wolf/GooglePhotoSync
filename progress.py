class progress:
    """
    Class for progress spinner

    Args:
        msg: message to send while progress is loading
        endmsg: message to end with after loading finishes

    Attributes:
        state: current status of progress bar (/, |, \, -)
    """

    def __init__(self, msg, endmsg):
        """
        Create the progress spinner, with the initial message and the spinner afterwards.
        """

        self.states = ["\\", "|", "/", "-"]
        self.state = 0
        self.msg = msg
        self.endmsg = endmsg

        print(self.msg + self.states[self.state], end="\r")

    def next(self, msg=""):
        """
        Progress the spinner
        """

        self.state += 1
        if self.state == 4:
            self.state = 0

        print(self.msg + self.states[self.state], end="\r")

    def finish(self):
        """
        Replaces spinner with end message
        """

        print(" " * (len(self.msg) + 1), end="\r")
        print(self.msg)
        print(self.endmsg, end="\n\n")