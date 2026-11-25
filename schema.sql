-- CS 5493/4243 Course Project: Part 1 Relational Schema
-- Project Title: Corporate Inventory & Supply Chain Management System
-- Authors: Phu Gia Pham & Ethan Ray Renaud

DROP TABLE IF EXISTS Supply_Request CASCADE;
DROP TABLE IF EXISTS Item CASCADE;
DROP TABLE IF EXISTS Employee CASCADE;
DROP TABLE IF EXISTS Department CASCADE;
DROP TABLE IF EXISTS Location CASCADE;
DROP TABLE IF EXISTS Supplier CASCADE;
DROP TABLE IF EXISTS Subcategory CASCADE;
DROP TABLE IF EXISTS Category CASCADE;

CREATE TABLE Category (
    CategoryName VARCHAR(64) PRIMARY KEY
);

CREATE TABLE Subcategory (
    SubcategoryName VARCHAR(64) PRIMARY KEY,
    CategoryName VARCHAR(64) NOT NULL,
    FOREIGN KEY (CategoryName) REFERENCES Category(CategoryName) ON DELETE RESTRICT
);

CREATE TABLE Supplier (
    SupplierID VARCHAR(16) PRIMARY KEY,
    SupplierName VARCHAR(128) NOT NULL
);

CREATE TABLE Location (
    LocationID VARCHAR(16) PRIMARY KEY,
    LocationName VARCHAR(128) NOT NULL UNIQUE
);

CREATE TABLE Department (
    DepartmentName VARCHAR(64) PRIMARY KEY
);

CREATE TABLE Employee (
    EmployeeName VARCHAR(128) PRIMARY KEY,
    DepartmentName VARCHAR(64) NOT NULL,
    FOREIGN KEY (DepartmentName) REFERENCES Department(DepartmentName) ON DELETE RESTRICT
);

CREATE TABLE Item (
    ItemID VARCHAR(16) PRIMARY KEY,
    ItemName VARCHAR(255) NOT NULL,
    UnitOfMeasure VARCHAR(32) DEFAULT 'unit',
    QuantityOnHand INT NOT NULL DEFAULT 0 CHECK (QuantityOnHand >= 0),
    ReorderLevel INT CHECK (ReorderLevel >= 0),
    TargetStockLevel INT CHECK (TargetStockLevel >= 0),
    EstimatedUnitCostUSD NUMERIC(10, 2) CHECK (EstimatedUnitCostUSD >= 0),
    InventoryValueUSD NUMERIC(12, 2) CHECK (InventoryValueUSD >= 0),
    StockStatus VARCHAR(32) DEFAULT 'In Stock',
    In_stock BOOLEAN DEFAULT TRUE,
    SubcategoryName VARCHAR(64) NOT NULL,
    SupplierID VARCHAR(16) NOT NULL,
    LocationID VARCHAR(16) NOT NULL,
    ManagedByEmployee VARCHAR(128) NOT NULL,
    FOREIGN KEY (SubcategoryName) REFERENCES Subcategory(SubcategoryName) ON DELETE RESTRICT,
    FOREIGN KEY (SupplierID) REFERENCES Supplier(SupplierID) ON DELETE RESTRICT,
    FOREIGN KEY (LocationID) REFERENCES Location(LocationID) ON DELETE RESTRICT,
    FOREIGN KEY (ManagedByEmployee) REFERENCES Employee(EmployeeName) ON DELETE RESTRICT
);

CREATE TABLE Supply_Request (
    RequestID VARCHAR(16) PRIMARY KEY,
    RequestDate DATE NOT NULL,
    RequestStatus VARCHAR(32) NOT NULL CHECK (RequestStatus IN ('Pending', 'Approved', 'Fulfilled', 'Rejected')),
    RequestedQuantity INT NOT NULL CHECK (RequestedQuantity > 0),
    SubmittedByEmployee VARCHAR(128) NOT NULL,
    ItemID VARCHAR(16) NOT NULL,
    FOREIGN KEY (SubmittedByEmployee) REFERENCES Employee(EmployeeName) ON DELETE RESTRICT,
    FOREIGN KEY (ItemID) REFERENCES Item(ItemID) ON DELETE RESTRICT
);
