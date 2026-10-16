class C {
 public text: str
 fn init(should_return: bool) {
  if should_return {
   return
  }
  this.text = "set"
 }
}
print(C(true).text)
