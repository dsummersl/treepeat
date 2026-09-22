-- A comprehensive Lua sample for testing similarity detection.
local socket = require("socket")

--[[
  Module table, the Lua equivalent of a class.
]]
local Comprehensive = {}

-- A method that will have a duplicate
function Comprehensive.calculateSum(a, b)
  local result = a + b
  print("Calculating sum: " .. result)
  return result
end

function Comprehensive:greet(name)
  local flag = true
  if flag and #name > 0 then
    print("Hello, " .. name)
  else
    print("Hello, stranger")
  end
  return self
end

local Another = {
  label = "another",
  count = 3,
  enabled = false,
}

-- Duplicate of calculateSum above
function Another.mySum(x, y)
  local z = x + y
  print("Calculating sum: " .. z)
  return z
end

Another.send = function(payload)
  return socket.send(payload)
end

return Comprehensive
